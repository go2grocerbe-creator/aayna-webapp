import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db import db, now_iso
from auth import get_current_admin

admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(get_current_admin)])

ORDER_STATUSES = ["New", "Confirmed", "Packed", "Sent to Courier", "Delivered", "Cancelled", "Returned"]


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
async def dashboard():
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    todays_orders = await db.orders.find({"created_at": {"$gte": today_start}}, {"_id": 0}).to_list(2000)
    sales_today = sum(o["total_amount"] for o in todays_orders if o.get("order_status") != "Cancelled")

    async def count(status):
        return await db.orders.count_documents({"order_status": status})

    low_stock = await db.products.count_documents({
        "status": {"$ne": "draft"},
        "$expr": {"$lte": ["$stock_quantity", "$low_stock_alert"]},
    })
    failed_notifications = await db.notification_logs.count_documents({"status": "failed"})

    return {
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


@admin_router.get("/products")
async def list_products(category: Optional[str] = None, status: Optional[str] = None, search: Optional[str] = None):
    q = {}
    if category:
        q["category_slug"] = category
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"product_name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]
    items = await db.products.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return items


@admin_router.get("/products/{product_id}")
async def get_product(product_id: str):
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


async def _category_name(slug):
    cat = await db.categories.find_one({"slug": slug}, {"_id": 0})
    return cat["name"] if cat else slug


@admin_router.post("/products")
async def create_product(payload: ProductPayload):
    if not payload.product_name or not payload.sku or not payload.category_slug:
        raise HTTPException(status_code=400, detail="Product name, SKU and category are required")
    if payload.selling_price is None or payload.stock_quantity is None:
        raise HTTPException(status_code=400, detail="Selling price and stock quantity are required")
    slug = payload.slug or slugify(payload.product_name)
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
        "short_description": payload.short_description or "",
        "full_description": payload.full_description or "",
        "cost_price": payload.cost_price or 0,
        "selling_price": payload.selling_price,
        "discount_price": payload.discount_price,
        "stock_quantity": payload.stock_quantity,
        "low_stock_alert": payload.low_stock_alert if payload.low_stock_alert is not None else 3,
        "material": payload.material or "", "color": payload.color or "", "size": payload.size or "",
        "weight": None,
        "status": payload.status or ("out_of_stock" if payload.stock_quantity <= 0 else "active"),
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
        await _log_inventory(doc["id"], "stock_in", doc["stock_quantity"], 0, doc["stock_quantity"], "Initial stock", None)
    return clean(doc)


@admin_router.put("/products/{product_id}")
async def update_product(product_id: str, payload: ProductPayload):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = payload.model_dump(exclude_unset=True)
    if "category_slug" in updates and updates["category_slug"]:
        updates["category_name"] = await _category_name(updates["category_slug"])

    new_stock = updates.get("stock_quantity")
    if new_stock is not None and new_stock != product.get("stock_quantity"):
        prev = int(product.get("stock_quantity", 0))
        await _log_inventory(product_id, "adjustment", new_stock - prev, prev, new_stock, "Edited via product form", None)
        if "status" not in updates:
            updates["status"] = "out_of_stock" if new_stock <= 0 else (
                "active" if product.get("status") == "out_of_stock" else product.get("status"))

    updates["updated_at"] = now_iso()
    await db.products.update_one({"id": product_id}, {"$set": updates})
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    return p


@admin_router.delete("/products/{product_id}")
async def deactivate_product(product_id: str):
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
async def list_categories():
    cats = await db.categories.find({}, {"_id": 0}).sort("sort_order", 1).to_list(200)
    for c in cats:
        c["product_count"] = await db.products.count_documents({"category_slug": c["slug"]})
    return cats


@admin_router.post("/categories")
async def create_category(payload: CategoryPayload):
    if not payload.name:
        raise HTTPException(status_code=400, detail="Category name is required")
    slug = payload.slug or slugify(payload.name)
    if await db.categories.find_one({"slug": slug}):
        raise HTTPException(status_code=400, detail="A category with this slug already exists")
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
async def update_category(category_id: str, payload: CategoryPayload):
    cat = await db.categories.find_one({"id": category_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = payload.model_dump(exclude_unset=True)
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
async def list_orders(status: Optional[str] = None, search: Optional[str] = None, limit: int = 500):
    q = {}
    if status and status != "all":
        q["order_status"] = status
    if search:
        q["$or"] = [
            {"order_number": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"customer_phone": {"$regex": search, "$options": "i"}},
        ]
    orders = await db.orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return orders


@admin_router.get("/orders/{order_number}")
async def get_order(order_number: str):
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    notifs = await db.notification_logs.find({"order_id": order_number}, {"_id": 0, "message": 0}).sort("created_at", -1).to_list(50)
    order["notifications"] = notifs
    return order


@admin_router.put("/orders/{order_number}")
async def update_order(order_number: str, payload: OrderUpdate):
    order = await db.orders.find_one({"order_number": order_number})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    updates = payload.model_dump(exclude_unset=True)
    if "order_status" in updates and updates["order_status"] not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid order status")
    updates["updated_at"] = now_iso()
    await db.orders.update_one({"order_number": order_number}, {"$set": updates})

    new_status = updates.get("order_status")
    if new_status and order.get("customer_id"):
        if new_status == "Delivered":
            await db.customers.update_one({"id": order["customer_id"]}, {"$inc": {"successful_orders": 1}})
        elif new_status == "Cancelled":
            await db.customers.update_one({"id": order["customer_id"]}, {"$inc": {"cancelled_orders": 1}})
    return await db.orders.find_one({"order_number": order_number}, {"_id": 0})


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
class StockAdjust(BaseModel):
    change_type: str  # stock_in | adjustment | damage | return
    quantity_change: int
    reason: Optional[str] = ""


async def _log_inventory(product_id, change_type, qty_change, prev, new, reason, ref):
    await db.inventory_logs.insert_one({
        "id": str(uuid.uuid4()), "product_id": product_id, "change_type": change_type,
        "quantity_change": qty_change, "previous_stock": prev, "new_stock": new,
        "reason": reason or "", "reference_order_id": ref, "created_by": "admin",
        "created_at": now_iso(),
    })


@admin_router.get("/inventory")
async def inventory(low_only: bool = False):
    q = {}
    if low_only:
        q = {"$expr": {"$lte": ["$stock_quantity", "$low_stock_alert"]}}
    products = await db.products.find(q, {"_id": 0, "cost_price": 0}).sort("stock_quantity", 1).to_list(1000)
    return products


@admin_router.post("/inventory/{product_id}/adjust")
async def adjust_stock(product_id: str, payload: StockAdjust):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    prev = int(product.get("stock_quantity", 0))
    new_stock = max(0, prev + payload.quantity_change)
    status = product.get("status")
    if new_stock <= 0:
        status = "out_of_stock"
    elif status == "out_of_stock":
        status = "active"
    await db.products.update_one({"id": product_id}, {"$set": {"stock_quantity": new_stock, "status": status, "updated_at": now_iso()}})
    await _log_inventory(product_id, payload.change_type, payload.quantity_change, prev, new_stock, payload.reason, None)
    return {"stock_quantity": new_stock, "status": status}


@admin_router.get("/inventory/{product_id}/logs")
async def inventory_logs(product_id: str):
    logs = await db.inventory_logs.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return logs


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@admin_router.get("/customers")
async def list_customers(search: Optional[str] = None):
    q = {}
    if search:
        q["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    customers = await db.customers.find(q, {"_id": 0}).sort("updated_at", -1).to_list(1000)
    for c in customers:
        last = await db.orders.find_one({"customer_id": c["id"]}, {"_id": 0, "created_at": 1, "order_number": 1}, sort=[("created_at", -1)])
        c["last_order_date"] = last["created_at"] if last else None
    return customers


@admin_router.get("/customers/{customer_id}")
async def customer_detail(customer_id: str):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = await db.orders.find({"customer_id": customer_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    customer["orders"] = orders
    return customer


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@admin_router.get("/settings")
async def get_all_settings():
    docs = await db.website_settings.find({}, {"_id": 0}).to_list(200)
    return {d["setting_key"]: d["setting_value"] for d in docs}


@admin_router.put("/settings")
async def update_settings(payload: dict):
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
async def export_products():
    products = await db.products.find({}, {"_id": 0}).to_list(2000)
    fields = ["product_name", "slug", "sku", "category_slug", "selling_price", "discount_price",
              "cost_price", "stock_quantity", "material", "color", "size", "status",
              "is_featured", "is_best_seller", "is_new_arrival", "short_description"]
    return _csv_response(products, fields, "aayna_products.csv")


@admin_router.get("/export/orders")
async def export_orders():
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
async def export_customers():
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
async def import_products(file: UploadFile = File(...)):
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
        if selling is None:
            errors.append(f"Row {idx}: invalid selling price")
            continue
        stock = _to_float(norm.get("stock quantity") or norm.get("stock_quantity")) or 0
        fields = {
            "product_name": name, "sku": sku, "category_slug": cat_slug, "category_name": cat_name,
            "selling_price": selling,
            "discount_price": _to_float(norm.get("discount price (bdt)") or norm.get("discount price") or norm.get("discount_price")),
            "cost_price": _to_float(norm.get("cost price estimate (bdt)") or norm.get("cost price") or norm.get("cost_price")) or 0,
            "stock_quantity": int(stock),
            "material": norm.get("material", ""), "color": norm.get("color", ""), "size": norm.get("size", ""),
            "short_description": norm.get("short description") or norm.get("short_description", ""),
            "full_description": norm.get("full description") or norm.get("full_description", ""),
            "status": (norm.get("status") or "active").lower(),
            "is_featured": _to_bool(norm.get("featured")), "is_best_seller": _to_bool(norm.get("best seller")),
            "is_new_arrival": _to_bool(norm.get("new arrival")),
            "updated_at": now_iso(),
        }
        existing = await db.products.find_one({"sku": sku})
        if existing:
            await db.products.update_one({"sku": sku}, {"$set": fields})
            updated += 1
        else:
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
