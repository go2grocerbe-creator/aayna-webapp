from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import os
import re
import uuid
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import httpx

from seed_data import SEED_CATEGORIES, SEED_PRODUCTS, SEED_SETTINGS, BD_DISTRICTS

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="AAYNA API")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger("aayna")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def effective_price(product: dict) -> float:
    dp = product.get("discount_price")
    if dp is not None and dp > 0:
        return float(dp)
    return float(product["selling_price"])


PHONE_RE = re.compile(r'^(?:\+?880|0)1[3-9]\d{8}$')


def normalize_phone(phone: str) -> Optional[str]:
    p = re.sub(r'[\s\-]', '', phone or '')
    if not PHONE_RE.match(p):
        return None
    digits = re.sub(r'\D', '', p)
    if digits.startswith('880'):
        digits = digits[3:]
    if digits.startswith('0'):
        digits = digits[1:]
    return '+880' + digits  # +8801XXXXXXXXX


PUBLIC_PRODUCT_HIDE = {"_id": 0, "cost_price": 0, "internal_notes": 0}

PAYMENT_MAP = {
    "cod": "Cash on Delivery",
    "bkash": "bKash Manual",
    "nagad": "Nagad Manual",
}


def public_product(p: dict) -> dict:
    p.pop("_id", None)
    p.pop("cost_price", None)
    p.pop("internal_notes", None)
    return p


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class CartLine(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class CartValidateRequest(BaseModel):
    items: List[CartLine]
    district: Optional[str] = None


class CheckoutRequest(BaseModel):
    customer_name: str
    customer_phone: str
    district: str
    delivery_address: str
    delivery_note: Optional[str] = ""
    customer_email: Optional[str] = ""
    payment_method: str  # cod | bkash | nagad
    transaction_id: Optional[str] = ""
    sender_number: Optional[str] = ""
    items: List[CartLine]
    client_request_id: Optional[str] = None


class TrackRequest(BaseModel):
    order_number: Optional[str] = None
    phone: Optional[str] = None


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
async def seed_database():
    if await db.categories.count_documents({}) == 0:
        await db.categories.insert_many([{**c} for c in SEED_CATEGORIES])
        logger.info("Seeded %d categories", len(SEED_CATEGORIES))

    if await db.products.count_documents({}) == 0:
        await db.products.insert_many([{**p} for p in SEED_PRODUCTS])
        logger.info("Seeded %d products", len(SEED_PRODUCTS))

    if await db.website_settings.count_documents({}) == 0:
        docs = [
            {"id": str(uuid.uuid4()), "setting_key": k, "setting_value": v,
             "created_at": now_iso(), "updated_at": now_iso()}
            for k, v in SEED_SETTINGS.items()
        ]
        await db.website_settings.insert_many(docs)
        logger.info("Seeded %d settings", len(docs))


@app.on_event("startup")
async def on_startup():
    await seed_database()


# ---------------------------------------------------------------------------
# Settings & meta
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"service": "AAYNA API", "status": "ok"}


@api_router.get("/settings")
async def get_settings():
    docs = await db.website_settings.find({}, {"_id": 0}).to_list(200)
    return {d["setting_key"]: d["setting_value"] for d in docs}


@api_router.get("/districts")
async def get_districts():
    return BD_DISTRICTS


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@api_router.get("/categories")
async def list_categories():
    cats = await db.categories.find({"status": "active"}, {"_id": 0}).sort("sort_order", 1).to_list(100)
    # attach product counts
    for c in cats:
        c["product_count"] = await db.products.count_documents(
            {"category_slug": c["slug"], "status": "active"})
    return cats


@api_router.get("/categories/{slug}")
async def get_category(slug: str):
    cat = await db.categories.find_one({"slug": slug}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@api_router.get("/products")
async def list_products(
    category: Optional[str] = None,
    sort: Optional[str] = "newest",
    featured: Optional[bool] = None,
    best_seller: Optional[bool] = None,
    new_arrival: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
):
    query: dict = {"status": {"$in": ["active", "out_of_stock"]}}
    if category:
        query["category_slug"] = category
    if featured is not None:
        query["is_featured"] = featured
    if best_seller is not None:
        query["is_best_seller"] = best_seller
    if new_arrival is not None:
        query["is_new_arrival"] = new_arrival
    if search:
        query["$or"] = [
            {"product_name": {"$regex": search, "$options": "i"}},
            {"short_description": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.products.find(query, PUBLIC_PRODUCT_HIDE)

    sort_map = {
        "newest": ("created_at", -1),
        "price_low": ("selling_price", 1),
        "price_high": ("selling_price", -1),
        "best_seller": ("is_best_seller", -1),
    }
    field, direction = sort_map.get(sort, ("created_at", -1))
    cursor = cursor.sort(field, direction)

    products = await cursor.to_list(limit)
    return products


@api_router.get("/products/{slug}")
async def get_product(slug: str):
    product = await db.products.find_one({"slug": slug}, PUBLIC_PRODUCT_HIDE)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    related = await db.products.find(
        {"category_slug": product["category_slug"], "slug": {"$ne": slug},
         "status": {"$in": ["active", "out_of_stock"]}},
        PUBLIC_PRODUCT_HIDE,
    ).limit(4).to_list(4)

    return {"product": product, "related": related}


# ---------------------------------------------------------------------------
# Cart validation (recalculates from DB)
# ---------------------------------------------------------------------------
def delivery_charge_for(settings: dict, district: str) -> int:
    if district and district.strip().lower() == "dhaka":
        return int(settings.get("delivery_charge_inside_dhaka", 80))
    return int(settings.get("delivery_charge_outside_dhaka", 130))


async def get_settings_map() -> dict:
    docs = await db.website_settings.find({}, {"_id": 0}).to_list(200)
    return {d["setting_key"]: d["setting_value"] for d in docs}


@api_router.post("/cart/validate")
async def validate_cart(req: CartValidateRequest):
    settings = await get_settings_map()
    lines = []
    subtotal = 0.0
    has_issue = False
    for line in req.items:
        product = await db.products.find_one({"id": line.product_id}, PUBLIC_PRODUCT_HIDE)
        if not product:
            lines.append({"product_id": line.product_id, "available": False,
                          "reason": "Product no longer available", "quantity": line.quantity})
            has_issue = True
            continue
        price = effective_price(product)
        stock = int(product.get("stock_quantity", 0))
        out_of_stock = stock <= 0 or product.get("status") == "out_of_stock"
        qty = min(line.quantity, stock) if stock > 0 else 0
        if out_of_stock or line.quantity > stock:
            has_issue = True
        line_total = price * qty
        subtotal += line_total
        lines.append({
            "product_id": product["id"],
            "slug": product["slug"],
            "name": product["product_name"],
            "sku": product["sku"],
            "image": (product.get("images") or [{}])[0].get("image_url"),
            "unit_price": price,
            "selling_price": product["selling_price"],
            "discount_price": product.get("discount_price"),
            "quantity": line.quantity,
            "available_quantity": stock,
            "out_of_stock": out_of_stock,
            "line_total": line_total,
            "available": not out_of_stock and line.quantity <= stock,
        })

    delivery = delivery_charge_for(settings, req.district) if req.district else 0
    return {
        "items": lines,
        "subtotal": subtotal,
        "delivery_charge": delivery,
        "total": subtotal + delivery,
        "has_issue": has_issue,
    }


# ---------------------------------------------------------------------------
# Order number counter
# ---------------------------------------------------------------------------
async def next_order_number() -> str:
    doc = await db.counters.find_one_and_update(
        {"_id": "order_number"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"ORD-{1000 + doc['seq']}"


# ---------------------------------------------------------------------------
# Notification (non-blocking, never cancels an order)
# ---------------------------------------------------------------------------
async def send_order_notification(order: dict):
    webhook_url = os.environ.get("MAKE_WEBHOOK_URL", "")
    payload = {
        "order_id": order["order_number"],
        "customer_name": order["customer_name"],
        "phone": order["customer_phone"],
        "email": order.get("customer_email") or "",
        "address": order["delivery_address"],
        "district": order["district"],
        "payment_method": order["payment_method"],
        "items": [
            {
                "product_name": it["product_name_snapshot"],
                "sku": it["sku_snapshot"],
                "quantity": it["quantity"],
                "unit_price": it["unit_price"],
                "total_price": it["total_price"],
            }
            for it in order["items"]
        ],
        "subtotal": order["subtotal"],
        "delivery_charge": order["delivery_charge"],
        "total": order["total_amount"],
        "order_status": order["order_status"],
        "created_at": order["created_at"],
    }

    log = {
        "id": str(uuid.uuid4()),
        "order_id": order["order_number"],
        "notification_type": "admin_webhook",
        "recipient": webhook_url or "MAKE_WEBHOOK_URL",
        "message": payload,
        "status": "pending",
        "error_message": None,
        "sent_at": None,
        "created_at": now_iso(),
    }

    if not webhook_url or webhook_url.strip().lower() == "placeholder":
        log["status"] = "failed"
        log["error_message"] = "MAKE_WEBHOOK_URL not configured (placeholder)"
        await db.notification_logs.insert_one(log)
        logger.warning("Notification skipped for %s: webhook not configured", order["order_number"])
        return

    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            resp = await cli.post(webhook_url, json=payload)
        if resp.status_code < 300:
            log["status"] = "sent"
            log["sent_at"] = now_iso()
        else:
            log["status"] = "failed"
            log["error_message"] = f"Webhook responded {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        log["status"] = "failed"
        log["error_message"] = str(exc)
        logger.warning("Notification failed for %s: %s", order["order_number"], exc)

    await db.notification_logs.insert_one(log)


# ---------------------------------------------------------------------------
# Checkout / order creation
# ---------------------------------------------------------------------------
@api_router.post("/checkout")
async def checkout(req: CheckoutRequest):
    # 1-2. Validate required fields
    if not req.customer_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")
    if not req.delivery_address.strip():
        raise HTTPException(status_code=400, detail="Delivery address is required")
    if req.district not in BD_DISTRICTS:
        raise HTTPException(status_code=400, detail="Please select a valid district")
    if req.payment_method not in PAYMENT_MAP:
        raise HTTPException(status_code=400, detail="Please select a valid payment method")
    if not req.items:
        raise HTTPException(status_code=400, detail="Your cart is empty")

    # 3. Validate phone
    phone = normalize_phone(req.customer_phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Please enter a valid Bangladesh phone number")

    # Idempotency: do not duplicate on refresh / double submit
    if req.client_request_id:
        existing = await db.orders.find_one({"client_request_id": req.client_request_id}, {"_id": 0})
        if existing:
            return {"order_number": existing["order_number"], "duplicate": True}

    # 4-5. Validate stock & recalc subtotal from DB
    order_items = []
    subtotal = 0.0
    stock_ops = []  # (product, qty)
    for line in req.items:
        product = await db.products.find_one({"id": line.product_id})
        if not product:
            raise HTTPException(status_code=400, detail="A product in your cart is no longer available")
        stock = int(product.get("stock_quantity", 0))
        if stock <= 0 or product.get("status") == "out_of_stock":
            raise HTTPException(status_code=400,
                                detail=f"{product['product_name']} is out of stock")
        if line.quantity > stock:
            raise HTTPException(status_code=400,
                                detail=f"Only {stock} left of {product['product_name']}")
        price = effective_price(product)
        line_total = price * line.quantity
        subtotal += line_total
        order_items.append({
            "id": str(uuid.uuid4()),
            "product_id": product["id"],
            "product_name_snapshot": product["product_name"],
            "sku_snapshot": product["sku"],
            "image": (product.get("images") or [{}])[0].get("image_url"),
            "quantity": line.quantity,
            "unit_price": price,
            "total_price": line_total,
        })
        stock_ops.append((product, line.quantity))

    # 6-7. Delivery + total
    settings = await get_settings_map()
    delivery_charge = delivery_charge_for(settings, req.district)
    total = subtotal + delivery_charge

    # 8. Upsert customer
    customer = await db.customers.find_one({"phone": phone})
    if customer:
        customer_id = customer["id"]
        await db.customers.update_one(
            {"id": customer_id},
            {"$set": {"full_name": req.customer_name, "default_address": req.delivery_address,
                      "district": req.district, "email": req.customer_email or customer.get("email"),
                      "updated_at": now_iso()},
             "$inc": {"total_orders": 1}},
        )
    else:
        customer_id = str(uuid.uuid4())
        await db.customers.insert_one({
            "id": customer_id, "full_name": req.customer_name, "phone": phone,
            "email": req.customer_email or "", "default_address": req.delivery_address,
            "district": req.district, "total_orders": 1, "successful_orders": 0,
            "cancelled_orders": 0, "created_at": now_iso(), "updated_at": now_iso(),
        })

    # 9-13. Create order
    order_number = await next_order_number()
    payment_method_display = PAYMENT_MAP[req.payment_method]
    payment_status = "COD_pending" if req.payment_method == "cod" else "pending"
    order = {
        "id": str(uuid.uuid4()),
        "order_number": order_number,
        "client_request_id": req.client_request_id,
        "customer_id": customer_id,
        "customer_name": req.customer_name,
        "customer_phone": phone,
        "customer_email": req.customer_email or "",
        "delivery_address": req.delivery_address,
        "district": req.district,
        "delivery_note": req.delivery_note or "",
        "subtotal": subtotal,
        "delivery_charge": delivery_charge,
        "discount_amount": 0,
        "total_amount": total,
        "payment_method": payment_method_display,
        "payment_status": payment_status,
        "order_status": "New",
        "transaction_id": req.transaction_id or "",
        "sender_number": req.sender_number or "",
        "courier_name": None,
        "courier_tracking_code": None,
        "admin_note": None,
        "notification_sent": False,
        "items": order_items,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.orders.insert_one({**order})

    # 11-12. Reduce stock + inventory log
    for product, qty in stock_ops:
        prev = int(product.get("stock_quantity", 0))
        new_stock = prev - qty
        new_status = "out_of_stock" if new_stock <= 0 else product.get("status", "active")
        await db.products.update_one(
            {"id": product["id"]},
            {"$set": {"stock_quantity": new_stock, "status": new_status, "updated_at": now_iso()}},
        )
        await db.inventory_logs.insert_one({
            "id": str(uuid.uuid4()), "product_id": product["id"], "change_type": "sale",
            "quantity_change": -qty, "previous_stock": prev, "new_stock": new_stock,
            "reason": "Order placed", "reference_order_id": order_number,
            "created_by": "system", "created_at": now_iso(),
        })

    # 14. Notification (non-blocking; failure never cancels order)
    try:
        await send_order_notification(order)
        await db.orders.update_one({"id": order["id"]}, {"$set": {"notification_sent": True}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notification error for %s: %s", order_number, exc)

    # 15. Return confirmation
    return {"order_number": order_number, "duplicate": False}


# ---------------------------------------------------------------------------
# Order confirmation (public-safe: no phone/address)
# ---------------------------------------------------------------------------
@api_router.get("/orders/{order_number}")
async def get_order_confirmation(order_number: str):
    order = await db.orders.find_one({"order_number": order_number}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_number": order["order_number"],
        "customer_name": order["customer_name"],
        "subtotal": order["subtotal"],
        "delivery_charge": order["delivery_charge"],
        "total_amount": order["total_amount"],
        "payment_method": order["payment_method"],
        "payment_status": order["payment_status"],
        "order_status": order["order_status"],
        "district": order["district"],
        "items": [
            {"product_name": it["product_name_snapshot"], "sku": it["sku_snapshot"],
             "quantity": it["quantity"], "unit_price": it["unit_price"],
             "total_price": it["total_price"], "image": it.get("image")}
            for it in order["items"]
        ],
        "created_at": order["created_at"],
    }


@api_router.post("/track")
async def track_order(req: TrackRequest):
    query = {}
    if req.order_number:
        query["order_number"] = req.order_number.strip().upper()
    elif req.phone:
        phone = normalize_phone(req.phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Please enter a valid order ID or phone number")
        query["customer_phone"] = phone
    else:
        raise HTTPException(status_code=400, detail="Enter an Order ID or phone number")

    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(20)
    if not orders:
        raise HTTPException(status_code=404, detail="No order found. Please check your details.")

    return [
        {
            "order_number": o["order_number"],
            "order_status": o["order_status"],
            "payment_method": o["payment_method"],
            "payment_status": o["payment_status"],
            "total_amount": o["total_amount"],
            "courier_name": o.get("courier_name"),
            "courier_tracking_code": o.get("courier_tracking_code"),
            "created_at": o["created_at"],
            "items": [
                {"product_name": it["product_name_snapshot"], "quantity": it["quantity"]}
                for it in o["items"]
            ],
        }
        for o in orders
    ]


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
