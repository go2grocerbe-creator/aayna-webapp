import csv
import io
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import db, now_iso
import emailer
import delivery
import product_content
from auth import get_current_admin, require, has_permission

admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(get_current_admin)])

ORDER_STATUSES = ["New", "Confirmed", "Packed", "Sent to Courier", "Delivered", "Cancelled", "Returned"]
# Meaningful changes the customer is emailed about (Packed is internal-only).
CUSTOMER_EMAIL_STATUSES = {"Confirmed": "Confirmed", "Sent to Courier": "Handed to courier",
                           "Delivered": "Delivered", "Cancelled": "Cancelled"}
PRODUCT_STATUSES = {"active", "draft", "inactive", "out_of_stock"}
# Business day boundary for "today" on the dashboard (Bangladesh, UTC+6, no DST).
BUSINESS_UTC_OFFSET = timedelta(hours=6)


def status_for_stock(current_status: str, new_stock: int) -> str:
    """Stock changes only toggle between the two public statuses. A draft or
    inactive product must never be published as a side effect of its stock
    reaching 0 (out_of_stock is a public, browsable status)."""
    if current_status in ("active", "out_of_stock"):
        return "out_of_stock" if new_stock <= 0 else "active"
    return current_status


def validate_product_fields(p: dict):
    """Raise 400 for values that would make a product unsellable or mis-priced."""
    price = p.get("selling_price")
    if price is None or price <= 0:
        raise HTTPException(status_code=400, detail="Selling price must be greater than 0")
    dp = p.get("discount_price")
    if dp is not None and dp != 0 and not (0 < dp < price):
        raise HTTPException(status_code=400, detail="Discount price must be above 0 and below the selling price (use 0 or leave blank for no discount)")
    if p.get("stock_quantity") is not None and p["stock_quantity"] < 0:
        raise HTTPException(status_code=400, detail="Stock quantity cannot be negative")
    if p.get("low_stock_alert") is not None and p["low_stock_alert"] < 0:
        raise HTTPException(status_code=400, detail="Low stock alert cannot be negative")
    if p.get("status") not in PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(sorted(PRODUCT_STATUSES))}")


# Admin-only internal fields: purchase cost and pricing/sourcing metadata. Only
# roles with "products.cost" (super_admin, admin) ever receive or change them.
PRIVATE_PRODUCT_FIELDS = ("cost_price", "internal_notes", "pricing", "price_history",
                          "previous_selling_price", "price_is_temporary", "source")
STOCK_CHANGE_TYPES = {"stock_in", "adjustment", "damage", "return"}


def for_role(product: dict, user: dict) -> dict:
    if product and not has_permission(user, "products.cost"):
        for f in PRIVATE_PRODUCT_FIELDS:
            product.pop(f, None)
    return product


def is_low_stock(p: dict) -> bool:
    try:
        return int(p.get("stock_quantity") or 0) <= int(p.get("low_stock_alert") if p.get("low_stock_alert") is not None else 3)
    except (TypeError, ValueError):
        return False


async def _low_stock_products(projection=None, include_drafts=False):
    # Compared in Python rather than with $expr: the catalogue is small, and this
    # works on every MongoDB-compatible server (the local test stand-in lacks $expr).
    q = {} if include_drafts else {"status": {"$ne": "draft"}}
    items = await db.products.find(q, projection or {"_id": 0}).to_list(5000)
    return [p for p in items if is_low_stock(p)]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or uuid.uuid4().hex[:8]


def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@admin_router.get("/dashboard")
async def dashboard(current=Depends(require("dashboard.view"))):
    # Midnight in Bangladesh, expressed in UTC (orders store UTC ISO timestamps).
    local_now = datetime.now(timezone.utc) + BUSINESS_UTC_OFFSET
    today_start = (local_now.replace(hour=0, minute=0, second=0, microsecond=0) - BUSINESS_UTC_OFFSET).isoformat()
    todays_orders = await db.orders.find({"created_at": {"$gte": today_start}}, {"_id": 0}).to_list(2000)
    sales_today = sum(o["total_amount"] for o in todays_orders if o.get("order_status") != "Cancelled")

    async def count(status):
        return await db.orders.count_documents({"order_status": status})

    low_stock = len(await _low_stock_products({"_id": 0, "stock_quantity": 1, "low_stock_alert": 1}))
    failed_notifications = await db.notification_logs.count_documents({"status": "failed"})

    # Catalogue + inventory figures straight from the database (no invented KPIs).
    product_status = {}
    units = 0
    async for p in db.products.find({}, {"_id": 0, "status": 1, "stock_quantity": 1}):
        product_status[p.get("status") or "unknown"] = product_status.get(p.get("status") or "unknown", 0) + 1
        units += int(p.get("stock_quantity") or 0)
    # Includes drafts so the owner sees low stock before publishing (labelled with status).
    low_stock_items = sorted(await _low_stock_products(
        {"_id": 0, "id": 1, "sku": 1, "product_name": 1, "stock_quantity": 1, "low_stock_alert": 1, "status": 1},
        include_drafts=True), key=lambda p: int(p.get("stock_quantity") or 0))[:20]
    recent_inventory = await db.inventory_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(8)
    names = {p["id"]: (p.get("product_name"), p.get("sku")) async for p in db.products.find(
        {"id": {"$in": [r.get("product_id") for r in recent_inventory]}}, {"_id": 0, "id": 1, "product_name": 1, "sku": 1})}
    for r in recent_inventory:
        r["product_name"], r["sku"] = names.get(r.get("product_id"), (None, None))
    recent_orders = await db.orders.find(
        {}, {"_id": 0, "order_number": 1, "customer_name": 1, "total_amount": 1, "order_status": 1,
             "payment_status": 1, "created_at": 1}).sort("created_at", -1).to_list(8)
    delivered_sales = 0.0
    async for o in db.orders.find({"order_status": "Delivered"}, {"_id": 0, "total_amount": 1}):
        delivered_sales += float(o.get("total_amount") or 0)

    return {
        "catalogue": {
            "total": sum(product_status.values()),
            "draft": product_status.get("draft", 0),
            "active": product_status.get("active", 0),
            "inactive": product_status.get("inactive", 0),
            "out_of_stock": product_status.get("out_of_stock", 0),
            "units_in_stock": units,
        },
        "low_stock_items": low_stock_items,
        "recent_inventory": recent_inventory,
        "recent_orders": recent_orders,
        "pending_orders": await db.orders.count_documents({"order_status": {"$in": ["New", "Confirmed", "Packed", "Sent to Courier"]}}),
        "delivered_sales_total": delivered_sales,
        "todays_orders": len(todays_orders),
        "new_orders": await count("New"),
        "confirmed_orders": await count("Confirmed"),
        "packed_orders": await count("Packed"),
        "delivered_orders": await count("Delivered"),
        "cancelled_orders": await count("Cancelled"),
        "total_sales_today": sales_today,
        "low_stock_count": low_stock,
        "failed_notifications": failed_notifications,
        "total_orders": await db.orders.count_documents({}),
        "total_products": await db.products.count_documents({}),
        "total_customers": await db.customers.count_documents({}),
    }


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductPayload(BaseModel):
    product_name: Optional[str] = None
    slug: Optional[str] = None
    sku: Optional[str] = None
    category_slug: Optional[str] = None
    short_description: Optional[str] = None
    full_description: Optional[str] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    discount_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    low_stock_alert: Optional[int] = None
    material: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    status: Optional[str] = None
    is_featured: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    is_new_arrival: Optional[bool] = None
    images: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    # Description & details (plain text, validated in product_content.py)
    highlights: Optional[list] = None
    care_note: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


def with_content_status(p: dict) -> dict:
    if p:
        p["content_status"] = product_content.completeness(p)
    return p


@admin_router.get("/products")
async def list_products(category: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None,
                        current=Depends(require("products.view"))):
    q = {}
    if category:
        q["category_slug"] = category
    if status:
        q["status"] = status
    if search:
        pattern = re.escape(search)
        q["$or"] = [
            {"product_name": {"$regex": pattern, "$options": "i"}},
            {"sku": {"$regex": pattern, "$options": "i"}},
        ]
    items = await db.products.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [with_content_status(for_role(i, current)) for i in items]


@admin_router.get("/products/{product_id}")
async def get_product(product_id: str, current=Depends(require("products.view"))):
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return with_content_status(for_role(p, current))


@admin_router.get("/products/{product_id}/content-history")
async def product_content_history(product_id: str, current=Depends(require("products.view"))):
    return await db.product_content_history.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(100)


async def _category_name(slug):
    cat = await db.categories.find_one({"slug": slug}, {"_id": 0})
    return cat["name"] if cat else slug


@admin_router.post("/products")
async def create_product(payload: ProductPayload, current=Depends(require("products.edit"))):
    if not payload.product_name or not payload.sku or not payload.category_slug:
        raise HTTPException(status_code=400, detail="Product name, SKU and category are required")
    if payload.selling_price is None or payload.stock_quantity is None:
        raise HTTPException(status_code=400, detail="Selling price and stock quantity are required")
    if payload.cost_price is not None and not has_permission(current, "products.cost"):
        raise HTTPException(status_code=403, detail="You do not have permission to set purchase costs")
    if await db.products.find_one({"sku": payload.sku.strip()}):
        raise HTTPException(status_code=409, detail="Another product already uses this SKU")
    # New products start as drafts unless a status is chosen explicitly.
    status = payload.status or "draft"
    validate_product_fields({**payload.model_dump(), "status": status})
    content = product_content.normalize_content(payload.model_dump())
    if status in ("active", "out_of_stock"):
        status = status_for_stock(status, payload.stock_quantity)
    slug = slugify(payload.slug) if payload.slug else slugify(payload.product_name)
    if await db.products.find_one({"slug": slug}):
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"
    doc = {
        "id": str(uuid.uuid4()),
        "product_name": payload.product_name,
        "slug": slug,
        "sku": payload.sku,
        "category_slug": payload.category_slug,
        "category_name": await _category_name(payload.category_slug),
        "category_id": None, "brand_id": None, "seller_id": None,
        "short_description": content.get("short_description", ""),
        "full_description": content.get("full_description", ""),
        "highlights": content.get("highlights", []),
        "care_note": content.get("care_note", ""),
        "seo_title": content.get("seo_title", ""),
        "seo_description": content.get("seo_description", ""),
        "cost_price": payload.cost_price or 0,
        "selling_price": payload.selling_price,
        "discount_price": payload.discount_price,
        "stock_quantity": payload.stock_quantity,
        "low_stock_alert": payload.low_stock_alert if payload.low_stock_alert is not None else 3,
        "material": content.get("material", ""), "color": payload.color or "", "size": content.get("size", ""),
        "weight": None,
        "status": status,
        "is_featured": bool(payload.is_featured),
        "is_best_seller": bool(payload.is_best_seller),
        "is_new_arrival": bool(payload.is_new_arrival),
        "tags": payload.tags or [],
        "images": payload.images or [],
        "internal_notes": "",
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.products.insert_one({**doc})
    if doc["stock_quantity"] > 0:
        await _log_inventory(doc["id"], "stock_in", doc["stock_quantity"], 0, doc["stock_quantity"], "Initial stock", None,
                             actor=current)
    return for_role(clean(doc), current)


@admin_router.put("/products/{product_id}")
async def update_product(product_id: str, payload: ProductPayload, current=Depends(require("products.edit"))):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = payload.model_dump(exclude_unset=True)
    # SKU is the product's identity (orders, inventory logs, importer): never changed here.
    if "sku" in updates and str(updates["sku"] or "").strip() != str(product.get("sku") or ""):
        raise HTTPException(status_code=400, detail="SKU cannot be changed")
    updates.pop("sku", None)
    if "cost_price" in updates and not has_permission(current, "products.cost"):
        if updates["cost_price"] != product.get("cost_price"):
            raise HTTPException(status_code=403, detail="You do not have permission to change purchase costs")
        updates.pop("cost_price")
    for required in ("product_name", "sku", "category_slug", "selling_price", "stock_quantity"):
        if required in updates and updates[required] in (None, ""):
            raise HTTPException(status_code=400, detail=f"{required.replace('_', ' ').capitalize()} cannot be empty")
    validate_product_fields({**product, **updates})
    updates.update(product_content.normalize_content(updates))
    if "slug" in updates:
        updates["slug"] = slugify(updates["slug"])
        if updates["slug"] != product.get("slug") and await db.products.find_one({"slug": updates["slug"], "id": {"$ne": product_id}}):
            raise HTTPException(status_code=409, detail="Another product already uses this URL slug")
    if "category_slug" in updates and updates["category_slug"]:
        updates["category_name"] = await _category_name(updates["category_slug"])

    new_stock = updates.get("stock_quantity")
    if new_stock is not None and new_stock != product.get("stock_quantity"):
        prev = int(product.get("stock_quantity", 0))
        await _log_inventory(product_id, "adjustment", new_stock - prev, prev, new_stock, "Edited via product form", None,
                             actor=current)
        if "status" not in updates:
            updates["status"] = status_for_stock(product.get("status"), new_stock)

    if updates.get("selling_price") is not None and updates["selling_price"] != product.get("selling_price"):
        updates["price_is_temporary"] = False  # founder set a real price (inventory import marker)

    updates["updated_at"] = now_iso()
    await db.products.update_one({"id": product_id}, {"$set": updates})
    await product_content.record_changes(db, product, updates, current.get("email"), updates["updated_at"])
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    return with_content_status(for_role(p, current))


@admin_router.delete("/products/{product_id}")
async def deactivate_product(product_id: str, current=Depends(require("products.delete"))):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    has_orders = await db.orders.find_one({"items.product_id": product_id})
    if has_orders:
        await db.products.update_one({"id": product_id}, {"$set": {"status": "inactive", "updated_at": now_iso()}})
        return {"deactivated": True, "deleted": False, "reason": "Product has order history — deactivated instead of deleted."}
    await db.products.delete_one({"id": product_id})
    return {"deactivated": False, "deleted": True}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
class CategoryPayload(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    sku_prefix: Optional[str] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None


@admin_router.get("/categories")
async def list_categories(current=Depends(require("products.view"))):
    cats = await db.categories.find({}, {"_id": 0}).sort("sort_order", 1).to_list(200)
    counts = await db.products.aggregate(
        [{"$group": {"_id": "$category_slug", "count": {"$sum": 1}}}]
    ).to_list(length=None)
    count_map = {c["_id"]: c["count"] for c in counts}
    for c in cats:
        c["product_count"] = count_map.get(c["slug"], 0)
    return cats


CATEGORY_STATUSES = {"active", "inactive"}


@admin_router.post("/categories")
async def create_category(payload: CategoryPayload, current=Depends(require("categories.edit"))):
    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Category name is required")
    if payload.status and payload.status not in CATEGORY_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")
    slug = slugify(payload.slug or payload.name)
    if await db.categories.find_one({"slug": slug}):
        raise HTTPException(status_code=409, detail="A category with this slug already exists")
    if await db.categories.find_one({"name": {"$regex": f"^{re.escape(payload.name.strip())}$", "$options": "i"}}):
        raise HTTPException(status_code=409, detail="A category with this name already exists")
    count = await db.categories.count_documents({})
    doc = {
        "id": str(uuid.uuid4()), "name": payload.name, "slug": slug,
        "description": payload.description or "", "image_url": payload.image_url or "",
        "sku_prefix": (payload.sku_prefix or slug[:3]).upper(), "parent_category_id": None,
        "status": payload.status or "active",
        "sort_order": payload.sort_order if payload.sort_order is not None else count + 1,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.categories.insert_one({**doc})
    return clean(doc)


@admin_router.put("/categories/{category_id}")
async def update_category(category_id: str, payload: CategoryPayload, current=Depends(require("categories.edit"))):
    cat = await db.categories.find_one({"id": category_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = payload.model_dump(exclude_unset=True)
    # The slug links products to their category: it is not editable here.
    if "slug" in updates and updates["slug"] != cat.get("slug"):
        raise HTTPException(status_code=400, detail="Category slug cannot be changed (products are linked by it)")
    updates.pop("slug", None)
    if "name" in updates:
        if not (updates["name"] or "").strip():
            raise HTTPException(status_code=400, detail="Category name is required")
        if await db.categories.find_one({"id": {"$ne": category_id},
                                         "name": {"$regex": f"^{re.escape(updates['name'].strip())}$", "$options": "i"}}):
            raise HTTPException(status_code=409, detail="A category with this name already exists")
    if "status" in updates and updates["status"] not in CATEGORY_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")
    if "sku_prefix" in updates and updates["sku_prefix"]:
        updates["sku_prefix"] = updates["sku_prefix"].upper()
    updates["updated_at"] = now_iso()
    await db.categories.update_one({"id": category_id}, {"$set": updates})
    # keep product category_name in sync
    if "name" in updates:
        await db.products.update_many({"category_slug": cat["slug"]}, {"$set": {"category_name": updates["name"]}})
    return await db.categories.find_one({"id": category_id}, {"_id": 0})


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderUpdate(BaseModel):
    order_status: Optional[str] = None
    courier_name: Optional[str] = None
    courier_tracking_code: Optional[str] = None
    admin_note: Optional[str] = None
    payment_status: Optional[str] = None


@admin_router.get("/orders")
async def list_orders(status: Optional[str] = None, search: Optional[str] = None, limit: int = 500,
                      current=Depends(require("orders.view"))):
    q = {}
    if status and status != "all":
        q["order_status"] = status
    if search:
        pattern = re.escape(search)
        q["$or"] = [
            {"order_number": {"$regex": pattern, "$options": "i"}},
            {"customer_name": {"$regex": pattern, "$options": "i"}},
            {"customer_phone": {"$regex": pattern, "$options": "i"}},
        ]
    hidden = {"_id": 0, "order_confirmation_token_hash": 0}
    if not has_permission(current, "courier.finance"):
        hidden["courier_finance"] = 0  # courier money is for super admins / admins only
    orders = await db.orders.find(q, hidden).sort("created_at", -1).to_list(limit)
    return orders


@admin_router.get("/orders/{order_number}")
async def get_order(order_number: str, current=Depends(require("orders.view"))):
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    notifs = await db.notification_logs.find({"order_id": order_number}, {"_id": 0, "message": 0}).sort("created_at", -1).to_list(50)
    order["notifications"] = notifs
    order["emails"] = await db.email_logs.find({"order_number": order_number}, {"_id": 0, "to_hash": 0, "dedupe_key": 0}).sort("created_at", -1).to_list(50)
    order["events"] = await db.order_events.find({"order_id": order.get("id")}, {"_id": 0}).sort("created_at", 1).to_list(100)
    order["redemptions"] = await db.promotion_redemptions.find({"order_id": order.get("id")}, {"_id": 0, "usage_key": 0, "usage_keys": 0}).to_list(10)
    order.pop("order_confirmation_token_hash", None)
    if not has_permission(current, "courier.finance"):
        order.pop("courier_finance", None)
    return order


@admin_router.put("/orders/{order_number}")
async def update_order(order_number: str, payload: OrderUpdate, current=Depends(require("orders.edit"))):
    order = await db.orders.find_one({"order_number": order_number})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    updates = payload.model_dump(exclude_unset=True)
    if "order_status" in updates and updates["order_status"] not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid order status")
    # A Steadfast booking owns the courier name and tracking code (Steadfast delivery panel).
    if (order.get("courier") or {}).get("state") in ("booking", "booked", "needs_reconciliation"):
        for k in ("courier_name", "courier_tracking_code"):
            if k in updates and (updates[k] or None) != (order.get(k) or None):
                raise HTTPException(status_code=409, detail="This order is booked with Steadfast: the courier and tracking code are managed in the Steadfast delivery panel.")
            updates.pop(k, None)
    updates["updated_at"] = now_iso()
    await db.orders.update_one({"order_number": order_number}, {"$set": updates})
    await order_status_side_effects(order, updates.get("order_status"), source="admin", actor=current["email"])
    return await db.orders.find_one({"order_number": order_number}, {"_id": 0})


async def order_status_side_effects(order: dict, new_status: Optional[str], source: str, actor: Optional[str]):
    """Counters, append-only history and the customer email for one status change.
    Shared by Admin -> Orders and the courier status sync (steadfast.py)."""
    order_number = order["order_number"]
    # Customer counters follow actual status transitions only, so saving the
    # same status twice (or moving an order out of Delivered/Cancelled) keeps
    # successful_orders / cancelled_orders accurate.
    old_status = order.get("order_status")
    if new_status and new_status != old_status and order.get("customer_id"):
        counter = {"Delivered": "successful_orders", "Cancelled": "cancelled_orders"}
        inc = {}
        if old_status in counter:
            inc[counter[old_status]] = -1
        if new_status in counter:
            inc[counter[new_status]] = inc.get(counter[new_status], 0) + 1
        if inc:
            await db.customers.update_one({"id": order["customer_id"]}, {"$inc": inc})
    if new_status and new_status != old_status:
        # Append-only history: the customer timeline shows only recorded transitions.
        await db.order_events.insert_one({"id": str(uuid.uuid4()), "order_id": order["id"], "order_number": order_number,
                                          "status": new_status, "previous_status": old_status, "source": source,
                                          "actor": actor, "created_at": now_iso()})
        if new_status in CUSTOMER_EMAIL_STATUSES and order.get("customer_email"):
            fresh = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
            link = f"/account/orders/{order_number}" if order.get("account_id") else f"/track-order?order={order_number}"
            try:
                await emailer.send("order_status", "order_status", order["customer_email"],
                                   {"name": order.get("customer_name"), "order": fresh, "label": CUSTOMER_EMAIL_STATUSES[new_status],
                                    "url": emailer.site_link(link)},
                                   dedupe_key=f"order_status:{order['id']}:{new_status}", account_id=order.get("account_id"),
                                   order_number=order_number)
            except Exception:  # noqa: BLE001 - a status change never fails because of email
                pass


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class StockAdjust(BaseModel):
    change_type: str  # stock_in | adjustment | damage | return
    quantity_change: int
    reason: Optional[str] = ""


async def _log_inventory(product_id, change_type, qty_change, prev, new, reason, ref, actor=None):
    await db.inventory_logs.insert_one({
        "id": str(uuid.uuid4()), "product_id": product_id, "change_type": change_type,
        "quantity_change": qty_change, "previous_stock": prev, "new_stock": new,
        "reason": reason or "", "reference_order_id": ref,
        "created_by": (actor or {}).get("email") or "admin",
        "created_at": now_iso(),
    })


@admin_router.get("/inventory")
async def inventory(low_only: bool = False, current=Depends(require("inventory.view"))):
    if low_only:
        # Same definition as the dashboard's low_stock_count (drafts excluded).
        products = sorted(await _low_stock_products({"_id": 0, "cost_price": 0}),
                          key=lambda p: int(p.get("stock_quantity") or 0))
    else:
        products = await db.products.find({}, {"_id": 0, "cost_price": 0}).sort("stock_quantity", 1).to_list(1000)
    return [for_role(p, current) for p in products]


@admin_router.post("/inventory/{product_id}/adjust")
async def adjust_stock(product_id: str, payload: StockAdjust, current=Depends(require("inventory.adjust"))):
    if payload.change_type not in STOCK_CHANGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Change type must be one of: {', '.join(sorted(STOCK_CHANGE_TYPES))}")
    if payload.quantity_change == 0:
        raise HTTPException(status_code=400, detail="Quantity change cannot be 0")
    if not (payload.reason or "").strip():
        raise HTTPException(status_code=400, detail="A reason is required for every stock adjustment")
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    prev = int(product.get("stock_quantity", 0))
    new_stock = prev + payload.quantity_change
    if new_stock < 0:
        raise HTTPException(status_code=400, detail=f"Stock cannot go below 0 (current stock is {prev})")
    status = status_for_stock(product.get("status"), new_stock)
    # Conditional write: only if stock is still what we read (a checkout in between
    # would otherwise be overwritten).
    res = await db.products.update_one({"id": product_id, "stock_quantity": product.get("stock_quantity")},
                                       {"$set": {"stock_quantity": new_stock, "status": status, "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Stock changed while you were editing. Reload and try again.")
    await _log_inventory(product_id, payload.change_type, payload.quantity_change, prev, new_stock,
                         payload.reason.strip(), None, actor=current)
    return {"stock_quantity": new_stock, "status": status}


@admin_router.get("/inventory/{product_id}/logs")
async def inventory_logs(product_id: str, current=Depends(require("inventory.view"))):
    logs = await db.inventory_logs.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return logs


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@admin_router.get("/customers")
async def list_customers(search: Optional[str] = None, current=Depends(require("customers.view"))):
    q = {}
    if search:
        pattern = re.escape(search)
        q["$or"] = [
            {"full_name": {"$regex": pattern, "$options": "i"}},
            {"phone": {"$regex": pattern, "$options": "i"}},
            {"email": {"$regex": pattern, "$options": "i"}},
        ]
    customers = await db.customers.find(q, {"_id": 0}).sort("updated_at", -1).to_list(1000)
    customer_ids = [c["id"] for c in customers]
    last_map = {}
    if customer_ids:
        # Latest order per customer, newest first (plain find: portable across
        # MongoDB-compatible servers and cheap at this catalogue's order volume).
        async for o in db.orders.find({"customer_id": {"$in": customer_ids}},
                                      {"_id": 0, "customer_id": 1, "created_at": 1}).sort("created_at", -1):
            last_map.setdefault(o["customer_id"], o.get("created_at"))
    for c in customers:
        c["last_order_date"] = last_map.get(c["id"])
    return customers


@admin_router.get("/customers/{customer_id}")
async def customer_detail(customer_id: str, current=Depends(require("customers.view"))):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = await db.orders.find({"customer_id": customer_id}, {"_id": 0, "courier_finance": 0, "order_confirmation_token_hash": 0}).sort("created_at", -1).to_list(200)
    customer["orders"] = orders
    return customer


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@admin_router.get("/settings")
async def get_all_settings(current=Depends(require("settings.view"))):
    docs = await db.website_settings.find({}, {"_id": 0}).to_list(200)
    return {d["setting_key"]: d["setting_value"] for d in docs}


SECRET_LIKE_KEY = re.compile(r"(secret|password|token|api_?key|mongo|jwt)", re.I)


@admin_router.put("/settings")
async def update_settings(payload: dict, current=Depends(require("settings.edit"))):
    bad = [k for k in payload if not isinstance(k, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", k) or SECRET_LIKE_KEY.search(k)]
    if bad:
        raise HTTPException(status_code=400, detail="Invalid setting key(s). Secrets belong in the hosting environment, never in settings.")
    for key, value in payload.items():
        problem = delivery.validate_setting(key, value)
        if key in ("steadfast_estimated_delivery_fee_bdt", "steadfast_estimated_cod_fee_pct") and value not in ("", None):
            hi = 5000 if key.endswith("_bdt") else 10
            ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= hi
            problem = None if ok else f"{key} must be empty or a number between 0 and {hi}"
        if problem:
            raise HTTPException(status_code=400, detail=problem)
    for key, value in payload.items():
        await db.website_settings.update_one(
            {"setting_key": key},
            {"$set": {"setting_value": value, "updated_at": now_iso()},
             "$setOnInsert": {"id": str(uuid.uuid4()), "setting_key": key, "created_at": now_iso()}},
            upsert=True,
        )
    docs = await db.website_settings.find({}, {"_id": 0}).to_list(200)
    return {d["setting_key"]: d["setting_value"] for d in docs}


# ---------------------------------------------------------------------------
# Export / Import CSV
# ---------------------------------------------------------------------------
def _csv_response(rows: List[dict], fields: List[str], filename: str):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_router.get("/export/products")
async def export_products(current=Depends(require("export.products"))):
    products = await db.products.find({}, {"_id": 0}).to_list(2000)
    fields = ["product_name", "slug", "sku", "category_slug", "selling_price", "discount_price",
              "cost_price", "stock_quantity", "material", "color", "size", "status",
              "is_featured", "is_best_seller", "is_new_arrival", "short_description"]
    return _csv_response(products, fields, "aayna_products.csv")


@admin_router.get("/export/orders")
async def export_orders(current=Depends(require("export.orders"))):
    orders = await db.orders.find({}, {"_id": 0}).to_list(5000)
    rows = []
    for o in orders:
        rows.append({**o, "items_summary": "; ".join(f"{i['product_name_snapshot']} x{i['quantity']}" for i in o.get("items", []))})
    fields = ["order_number", "created_at", "customer_name", "customer_phone", "district",
              "delivery_address", "subtotal", "delivery_charge", "total_amount",
              "payment_method", "payment_status", "order_status", "courier_name",
              "courier_tracking_code", "items_summary"]
    return _csv_response(rows, fields, "aayna_orders.csv")


@admin_router.get("/export/customers")
async def export_customers(current=Depends(require("export.customers"))):
    customers = await db.customers.find({}, {"_id": 0}).to_list(5000)
    fields = ["full_name", "phone", "email", "district", "total_orders", "successful_orders", "cancelled_orders", "created_at"]
    return _csv_response(customers, fields, "aayna_customers.csv")


def _to_float(v):
    try:
        return float(str(v).strip()) if str(v).strip() not in ("", "None") else None
    except Exception:
        return None


def _to_bool(v):
    return str(v).strip().lower() in ("yes", "true", "1", "y")


@admin_router.post("/import/products")
async def import_products(file: UploadFile = File(...), current=Depends(require("import.products"))):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created, updated, errors = 0, 0, []
    for idx, row in enumerate(reader, start=2):
        norm = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
        name = norm.get("product name") or norm.get("product_name")
        sku = norm.get("sku")
        if not name or not sku:
            errors.append(f"Row {idx}: missing product name or SKU")
            continue
        cat_field = norm.get("category") or norm.get("category_slug") or ""
        cat = await db.categories.find_one({"$or": [{"name": {"$regex": f"^{re.escape(cat_field)}$", "$options": "i"}}, {"slug": slugify(cat_field)}]})
        cat_slug = cat["slug"] if cat else slugify(cat_field)
        cat_name = cat["name"] if cat else cat_field
        selling = _to_float(norm.get("selling price (bdt)") or norm.get("selling price") or norm.get("selling_price"))
        if selling is None or selling <= 0:
            errors.append(f"Row {idx}: invalid selling price")
            continue
        stock = _to_float(norm.get("stock quantity") or norm.get("stock_quantity")) or 0
        if stock < 0:
            errors.append(f"Row {idx}: stock quantity cannot be negative")
            continue
        status_in = (norm.get("status") or "").lower()
        if status_in and status_in not in PRODUCT_STATUSES:
            errors.append(f"Row {idx}: unknown status '{status_in}' (use {', '.join(sorted(PRODUCT_STATUSES))})")
            continue
        discount = _to_float(norm.get("discount price (bdt)") or norm.get("discount price") or norm.get("discount_price"))
        if discount is not None and discount != 0 and not (0 < discount < selling):
            errors.append(f"Row {idx}: discount price must be below the selling price")
            continue
        fields = {
            "product_name": name, "sku": sku, "category_slug": cat_slug, "category_name": cat_name,
            "selling_price": selling,
            "discount_price": discount,
            "stock_quantity": int(stock),
            "material": norm.get("material", ""), "color": norm.get("color", ""), "size": norm.get("size", ""),
            "short_description": norm.get("short description") or norm.get("short_description", ""),
            "full_description": norm.get("full description") or norm.get("full_description", ""),
            "is_featured": _to_bool(norm.get("featured")), "is_best_seller": _to_bool(norm.get("best seller")),
            "is_new_arrival": _to_bool(norm.get("new arrival")),
            "updated_at": now_iso(),
        }
        try:
            fields.update(product_content.normalize_content(
                {k: fields[k] for k in ("material", "size", "short_description", "full_description")}))
        except HTTPException as e:
            errors.append(f"Row {idx}: {e.detail}")
            continue
        cost = _to_float(norm.get("cost price estimate (bdt)") or norm.get("cost price") or norm.get("cost_price"))
        if cost is not None and has_permission(current, "products.cost"):
            fields["cost_price"] = cost
        existing = await db.products.find_one({"sku": sku})
        if existing:
            # An update never blanks existing text, and stock on an existing
            # product only changes through the inventory workflow (logged).
            for k in ("material", "color", "size", "short_description", "full_description"):
                if not fields.get(k):
                    fields.pop(k, None)
            if int(stock) != int(existing.get("stock_quantity") or 0):
                errors.append(f"Row {idx}: stock for existing SKU {sku} not changed - use Inventory to adjust stock")
            fields.pop("stock_quantity", None)
            stock = existing.get("stock_quantity") or 0
            # Status changes only when the CSV says so; otherwise a re-import must
            # never publish a draft/inactive product (stock may still toggle
            # active <-> out_of_stock).
            fields["status"] = status_in or status_for_stock(existing.get("status"), int(stock))
            await db.products.update_one({"sku": sku}, {"$set": fields})
            updated += 1
        else:
            fields.setdefault("cost_price", 0)
            fields["status"] = status_for_stock(status_in or "draft", int(stock))
            slug = norm.get("slug") or slugify(name)
            if await db.products.find_one({"slug": slug}):
                slug = f"{slug}-{uuid.uuid4().hex[:4]}"
            await db.products.insert_one({
                "id": str(uuid.uuid4()), "slug": slug, "low_stock_alert": 3, "tags": [],
                "images": [], "internal_notes": "", "category_id": None, "brand_id": None,
                "seller_id": None, "weight": None, "created_at": now_iso(), **fields,
            })
            created += 1
    return {"created": created, "updated": updated, "errors": errors}
