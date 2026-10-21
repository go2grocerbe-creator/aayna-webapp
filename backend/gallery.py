"""Product photo order and cover selection (21 Oct 2026, founder kit `gallery_contract.py`).

Phase 1 (this module): the 31 reviewed static photos (/product-images/..., listed per SKU in
static_gallery_data.py) can be reordered per product; the FIRST photo is the cover everywhere
(catalogue cards, product page, cart, order snapshot, SEO/social image). Only the order is stored
on the product (`gallery_order` = list of photo URLs, `gallery_revision` = optimistic-lock counter);
no file is copied, moved or deleted.

Writes are a compare-and-set on `gallery_revision`: a save based on an older revision gets 409 and
the admin reloads. Every change is appended to `product_gallery_history` (who, when, before, after).

Phase 2 (uploads) needs persistent object storage (Cloudflare R2 recommended, see
docs/IMAGE_STORAGE_ARCHITECTURE.md in the founder kit). It is OFF until IMAGE_UPLOADS_ENABLED and the
R2_* settings exist; the upload endpoint then still refuses until the R2 integration is built - it
never pretends an upload worked.
"""
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require
from db import db, now_iso
import gallery_contract as gc
from static_gallery_data import STATIC_GALLERY

gallery_router = APIRouter(prefix="/api/admin")

R2_SETTINGS = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE_URL")
SETUP_GUIDANCE = ("New photo uploads need permanent image storage. Create a Cloudflare R2 bucket with a "
                  "read/write token limited to it, then add R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, "
                  "R2_SECRET_ACCESS_KEY and R2_PUBLIC_BASE_URL (and IMAGE_UPLOADS_ENABLED=true) to the server "
                  "settings. Until then, existing photos can be reordered and the cover chosen.")


def uploads_status() -> dict:
    """Never claims uploads work. Names of missing settings only, never values."""
    if (os.environ.get("IMAGE_UPLOADS_ENABLED") or "").strip().lower() not in ("1", "true", "yes"):
        return {"enabled": False, "reason": "Photo uploads are switched off (no permanent image storage configured).",
                "setup": SETUP_GUIDANCE}
    missing = [k for k in R2_SETTINGS if not (os.environ.get(k) or "").strip()]
    if missing:
        return {"enabled": False, "reason": "Image storage is not fully configured: " + ", ".join(missing) + " missing.",
                "setup": SETUP_GUIDANCE}
    return {"enabled": False, "reason": "Image storage settings exist, but the R2 upload integration is not built in this "
                                        "version yet.", "setup": SETUP_GUIDANCE}


def _db_images(product: dict) -> List[dict]:
    imgs = [(i, im or {}) for i, im in enumerate(product.get("images") or [])]
    imgs = [(i, im) for i, im in imgs if isinstance(im.get("image_url"), str) and im["image_url"].strip()]
    imgs.sort(key=lambda t: (0 if t[1].get("is_main") else 1, float(t[1].get("sort_order") or 0), t[0]))
    return [im for _, im in imgs]


def static_gallery(product: dict) -> List[dict]:
    """The product's reviewed static photos in the saved order (new photos appended, unknown URLs ignored)."""
    base = STATIC_GALLERY.get(str(product.get("sku") or "").strip(), [])
    items = gc.normalize_legacy([p["src"] for p in base])
    srcset = {p["src"]: p.get("srcSet", "") for p in base}
    order = [u for u in (product.get("gallery_order") or []) if isinstance(u, str)]
    rank = {u: k for k, u in enumerate(order)}
    items.sort(key=lambda it: (rank.get(it["url"], len(order)), it["position"]))
    return [{**it, "position": k, "srcSet": srcset.get(it["url"], "")} for k, it in enumerate(items)]


def cover_url(product: dict):
    """The one cover rule for server-side uses (order snapshots, cart lines): uploaded DB images
    first (is_main, sort_order), otherwise the first static photo in the saved order."""
    dbi = _db_images(product)
    if dbi:
        return dbi[0]["image_url"]
    st = static_gallery(product)
    return st[0]["url"] if st else None


def _view(product: dict) -> dict:
    dbi = _db_images(product)
    if dbi:
        images = [{"id": f"db_{k}", "url": im["image_url"], "alt": im.get("alt_text") or "", "source": "database", "position": k}
                  for k, im in enumerate(dbi)]
        source, editable = "database", False
    else:
        images = [{k: v for k, v in it.items()} for it in static_gallery(product)]
        source, editable = "static", True
    return {"product_id": product.get("id"), "sku": product.get("sku"), "revision": int(product.get("gallery_revision") or 0),
            "source": source, "editable": editable, "images": images, "cover": images[0]["url"] if images else None,
            "uploads": uploads_status()}


async def _product(product_id: str) -> dict:
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


class GalleryOrder(BaseModel):
    expected_revision: int = Field(..., ge=0)
    ordered_ids: List[str] = Field(..., max_length=gc.MAX_IMAGES)


@gallery_router.get("/products/{product_id}/gallery")
async def get_gallery(product_id: str, current=Depends(require("products.view"))):
    return _view(await _product(product_id))


@gallery_router.put("/products/{product_id}/gallery/order")
async def save_gallery_order(product_id: str, body: GalleryOrder, current=Depends(require("products.edit"))):
    product = await _product(product_id)
    if _db_images(product):
        raise HTTPException(status_code=409, detail="This product uses uploaded images; change their order in the Images section.")
    revision = int(product.get("gallery_revision") or 0)
    if body.expected_revision != revision:
        raise HTTPException(status_code=409, detail="The photo order was changed by someone else. Reload to see the latest order.")
    before = static_gallery(product)
    try:
        new = gc.apply_order([{k: it[k] for k in ("id", "url", "source", "alt", "position")} for it in before], body.ordered_ids)
    except gc.GalleryError as e:
        raise HTTPException(status_code=409 if "reload" in str(e) else 400, detail=str(e))
    urls = [it["url"] for it in new]
    at = now_iso()
    guard = {"id": product_id, "gallery_revision": revision} if revision else \
        {"id": product_id, "$or": [{"gallery_revision": {"$exists": False}}, {"gallery_revision": 0}]}
    res = await db.products.update_one(guard, {"$set": {"gallery_order": urls, "gallery_revision": revision + 1,
                                                        "gallery_updated_at": at, "updated_at": at}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="The photo order was changed by someone else. Reload to see the latest order.")
    await db.product_gallery_history.insert_one({
        "id": str(uuid.uuid4()), "product_id": product_id, "sku": product.get("sku"), "actor": current.get("email"),
        "revision": revision + 1, "before": [it["url"] for it in before], "after": urls,
        "cover_before": before[0]["url"] if before else None, "cover_after": urls[0] if urls else None, "created_at": at})
    return _view(await _product(product_id))


@gallery_router.get("/products/{product_id}/gallery/history")
async def gallery_history(product_id: str, current=Depends(require("products.view"))):
    return await db.product_gallery_history.find({"product_id": product_id}, {"_id": 0}).sort("created_at", -1).to_list(50)


@gallery_router.post("/products/{product_id}/gallery/upload-intent")
async def gallery_upload_intent(product_id: str, current=Depends(require("products.edit"))):
    await _product(product_id)
    st = uploads_status()
    raise HTTPException(status_code=503, detail=st["reason"] + " " + st["setup"])
