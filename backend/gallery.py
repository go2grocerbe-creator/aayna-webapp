"""Secure product gallery ordering and Cloudflare R2 uploads."""

import asyncio
import io
import logging
import os
import secrets
import uuid
from typing import List
from urllib.parse import quote, urlparse

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from auth import require
from db import db, now_iso
import gallery_contract as gc
from static_gallery_data import STATIC_GALLERY

gallery_router = APIRouter(prefix="/api/admin")
logger = logging.getLogger("aayna.gallery")
R2_SETTINGS = (
    "R2_ACCOUNT_ID",
    "R2_BUCKET",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_PUBLIC_BASE_URL",
)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PRODUCT_IMAGES = 12
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}
SETUP_GUIDANCE = (
    "Configure R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and "
    "R2_PUBLIC_BASE_URL, then set IMAGE_UPLOADS_ENABLED=true."
)


def _enabled(value):
    return (value or "").strip().lower() in ("1", "true", "yes")


def uploads_status() -> dict:
    if not _enabled(os.environ.get("IMAGE_UPLOADS_ENABLED")):
        return {
            "enabled": False,
            "reason": "Photo uploads are switched off.",
            "setup": SETUP_GUIDANCE,
        }
    missing = [key for key in R2_SETTINGS if not (os.environ.get(key) or "").strip()]
    if missing:
        return {
            "enabled": False,
            "reason": "Image storage is not fully configured: "
            + ", ".join(missing)
            + " missing.",
            "setup": SETUP_GUIDANCE,
        }
    parsed = urlparse(os.environ["R2_PUBLIC_BASE_URL"].strip().rstrip("/"))
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return {
            "enabled": False,
            "reason": "R2_PUBLIC_BASE_URL must be a clean HTTPS origin.",
            "setup": SETUP_GUIDANCE,
        }
    return {"enabled": True, "reason": "", "setup": ""}


def _require_uploads():
    status = uploads_status()
    if not status["enabled"]:
        raise HTTPException(
            status_code=503, detail=status["reason"] + " " + status["setup"]
        )


def _r2_client():
    account = os.environ["R2_ACCOUNT_ID"].strip()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"].strip(),
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"].strip(),
        region_name="auto",
        config=Config(
            signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"}
        ),
    )


def _put_r2(key, data, content_type):
    _r2_client().put_object(
        Bucket=os.environ["R2_BUCKET"].strip(),
        Key=key,
        Body=data,
        ContentType=content_type,
        IfNoneMatch="*",
        CacheControl="public, max-age=31536000, immutable",
        Metadata={"application": "aayna", "asset-type": "product-image"},
    )


def _delete_r2(key):
    _r2_client().delete_object(Bucket=os.environ["R2_BUCKET"].strip(), Key=key)


def _inspect_image(data, declared_type):
    if not data:
        raise HTTPException(status_code=400, detail="The selected file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Images must be 5 MB or smaller.")
    if declared_type not in {value[0] for value in ALLOWED_FORMATS.values()}:
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG and WebP images are supported."
        )
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            fmt, width, height = image.format, image.width, image.height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="The file is not a valid image.")
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG and WebP images are supported."
        )
    content_type, ext = ALLOWED_FORMATS[fmt]
    if declared_type != content_type:
        raise HTTPException(
            status_code=400, detail="The file type does not match the image content."
        )
    if width < 100 or height < 100 or width * height > 25_000_000:
        raise HTTPException(
            status_code=400,
            detail="Image dimensions must be at least 100×100 and no more than 25 megapixels.",
        )
    return content_type, ext, width, height


def _db_images(product: dict) -> List[dict]:
    images = [
        (index, image or {}) for index, image in enumerate(product.get("images") or [])
    ]
    images = [
        (index, image)
        for index, image in images
        if isinstance(image.get("image_url"), str) and image["image_url"].strip()
    ]
    images.sort(
        key=lambda item: (
            0 if item[1].get("is_main") else 1,
            float(item[1].get("sort_order") or 0),
            item[0],
        )
    )
    return [image for _, image in images]


def static_gallery(product: dict) -> List[dict]:
    base = STATIC_GALLERY.get(str(product.get("sku") or "").strip(), [])
    items = gc.normalize_legacy([photo["src"] for photo in base])
    srcset = {photo["src"]: photo.get("srcSet", "") for photo in base}
    order = [
        url for url in (product.get("gallery_order") or []) if isinstance(url, str)
    ]
    rank = {url: index for index, url in enumerate(order)}
    items.sort(key=lambda item: (rank.get(item["url"], len(order)), item["position"]))
    return [
        {**item, "position": index, "srcSet": srcset.get(item["url"], "")}
        for index, item in enumerate(items)
    ]


def _items(product: dict) -> List[dict]:
    db_images = _db_images(product)
    if not db_images:
        return static_gallery(product)
    result = []
    for index, image in enumerate(db_images):
        url = image["image_url"]
        result.append(
            {
                "id": image.get("id") or gc.stable_id(url),
                "url": url,
                "alt": image.get("alt_text") or "",
                "source": image.get("source")
                or ("r2" if image.get("object_key") else "database"),
                "position": index,
                "content_type": image.get("content_type"),
                "size": image.get("size"),
                "width": image.get("width"),
                "height": image.get("height"),
            }
        )
    return result


def cover_url(product: dict):
    items = _items(product)
    return items[0]["url"] if items else None


def _view(product: dict) -> dict:
    images = _items(product)
    return {
        "product_id": product.get("id"),
        "sku": product.get("sku"),
        "revision": int(product.get("gallery_revision") or 0),
        "source": "database" if _db_images(product) else "static",
        "editable": True,
        "images": images,
        "cover": images[0]["url"] if images else None,
        "uploads": uploads_status(),
        "max_images": MAX_PRODUCT_IMAGES,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
    }


async def _product(product_id):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _stored_images(items, product):
    existing = {
        image.get("id") or gc.stable_id(image.get("image_url", "")): image
        for image in _db_images(product)
    }
    stored = []
    for index, item in enumerate(items):
        old = existing.get(item["id"], {})
        stored.append(
            {
                **old,
                "id": item["id"],
                "image_url": item["url"],
                "alt_text": item.get("alt", ""),
                "source": item.get("source", "static"),
                "is_main": index == 0,
                "sort_order": index,
            }
        )
    return stored


async def _audit(product, current, action, before, after, revision, **extra):
    await db.product_gallery_history.insert_one(
        {
            "id": str(uuid.uuid4()),
            "product_id": product["id"],
            "sku": product.get("sku"),
            "actor": current.get("email"),
            "action": action,
            "revision": revision,
            "before": [item["url"] for item in before],
            "after": [item["url"] for item in after],
            "cover_before": before[0]["url"] if before else None,
            "cover_after": after[0]["url"] if after else None,
            "created_at": now_iso(),
            **extra,
        }
    )


def _public_hosts():
    host = urlparse((os.environ.get("R2_PUBLIC_BASE_URL") or "").strip()).hostname
    return (host,) if host else ()


class GalleryOrder(BaseModel):
    expected_revision: int = Field(..., ge=0)
    ordered_ids: List[str] = Field(..., max_length=MAX_PRODUCT_IMAGES)


class GalleryDelete(BaseModel):
    expected_revision: int = Field(..., ge=0)


@gallery_router.get("/products/{product_id}/gallery")
async def get_gallery(product_id: str, current=Depends(require("products.view"))):
    return _view(await _product(product_id))


@gallery_router.put("/products/{product_id}/gallery/order")
async def save_gallery_order(
    product_id: str, body: GalleryOrder, current=Depends(require("products.edit"))
):
    product = await _product(product_id)
    revision = int(product.get("gallery_revision") or 0)
    if body.expected_revision != revision:
        raise HTTPException(
            status_code=409, detail="The photo gallery changed. Reload and try again."
        )
    before = _items(product)
    try:
        new = gc.apply_order(
            [
                {key: item[key] for key in ("id", "url", "source", "alt", "position")}
                for item in before
            ],
            body.ordered_ids,
            _public_hosts(),
        )
    except gc.GalleryError as error:
        raise HTTPException(
            status_code=409 if "reload" in str(error) else 400, detail=str(error)
        )
    at = now_iso()
    guard = (
        {"id": product_id, "gallery_revision": revision}
        if revision
        else {
            "id": product_id,
            "$or": [{"gallery_revision": {"$exists": False}}, {"gallery_revision": 0}],
        }
    )
    updates = {
        "gallery_order": [item["url"] for item in new],
        "gallery_revision": revision + 1,
        "gallery_updated_at": at,
        "updated_at": at,
    }
    # Keep the 31 approved built-in photos as static assets until the first R2
    # upload. Once a product has stored gallery records, reorder those records.
    if _db_images(product):
        updates["images"] = _stored_images(new, product)
    result = await db.products.update_one(guard, {"$set": updates})
    if result.modified_count != 1:
        raise HTTPException(
            status_code=409, detail="The photo gallery changed. Reload and try again."
        )
    await _audit(product, current, "reorder", before, new, revision + 1)
    return _view(await _product(product_id))


@gallery_router.post("/products/{product_id}/gallery/images")
async def upload_gallery_image(
    product_id: str,
    expected_revision: int = Form(...),
    request_id: str = Form(...),
    file: UploadFile = File(...),
    current=Depends(require("products.edit")),
):
    _require_uploads()
    if not (8 <= len(request_id) <= 100) or not all(
        char.isalnum() or char in "-_" for char in request_id
    ):
        raise HTTPException(
            status_code=400, detail="Invalid upload request identifier."
        )
    product = await _product(product_id)
    if request_id in (product.get("gallery_upload_request_ids") or []):
        return _view(product)
    revision = int(product.get("gallery_revision") or 0)
    if expected_revision != revision:
        raise HTTPException(
            status_code=409,
            detail="The photo gallery changed. Reload before uploading.",
        )
    before = _items(product)
    if len(before) >= MAX_PRODUCT_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"A product can have at most {MAX_PRODUCT_IMAGES} images.",
        )
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    content_type, ext, width, height = _inspect_image(data, file.content_type)
    image_id = "r2_" + secrets.token_hex(16)
    key = f"products/{quote(str(product.get('sku') or product_id), safe='')}/{uuid.uuid4().hex}-{secrets.token_hex(8)}.{ext}"
    url = os.environ["R2_PUBLIC_BASE_URL"].strip().rstrip("/") + "/" + key
    try:
        await asyncio.to_thread(_put_r2, key, data, content_type)
    except Exception as error:
        logger.exception(
            "R2 upload failed for product %s: %s", product_id, type(error).__name__
        )
        raise HTTPException(
            status_code=502,
            detail="R2 rejected the upload. Check storage configuration and try again.",
        )
    item = {
        "id": image_id,
        "url": url,
        "alt": (file.filename or product.get("product_name") or "Product image")[
            : gc.MAX_ALT
        ],
        "source": "r2",
        "position": len(before),
        "object_key": key,
        "content_type": content_type,
        "size": len(data),
        "width": width,
        "height": height,
    }
    new = before + [item]
    stored = _stored_images(new, product)
    stored[-1].update(
        {
            name: item[name]
            for name in ("object_key", "content_type", "size", "width", "height")
        }
    )
    at = now_iso()
    rev_guard = (
        {"gallery_revision": revision}
        if revision
        else {
            "$or": [{"gallery_revision": {"$exists": False}}, {"gallery_revision": 0}]
        }
    )
    guard = {
        "id": product_id,
        "gallery_upload_request_ids": {"$ne": request_id},
        **rev_guard,
    }
    result = await db.products.update_one(
        guard,
        {
            "$set": {
                "images": stored,
                "gallery_order": [i["url"] for i in new],
                "gallery_revision": revision + 1,
                "gallery_updated_at": at,
                "updated_at": at,
            },
            "$push": {
                "gallery_upload_request_ids": {"$each": [request_id], "$slice": -50}
            },
        },
    )
    if result.modified_count != 1:
        try:
            await asyncio.to_thread(_delete_r2, key)
        except Exception:
            logger.exception("Could not clean up unreferenced R2 object %s", key)
        fresh = await _product(product_id)
        if request_id in (fresh.get("gallery_upload_request_ids") or []):
            return _view(fresh)
        raise HTTPException(
            status_code=409,
            detail="The photo gallery changed during upload. The unused upload was removed; retry.",
        )
    await _audit(
        product,
        current,
        "upload",
        before,
        new,
        revision + 1,
        image_id=image_id,
        object_key=key,
        content_type=content_type,
        size=len(data),
        width=width,
        height=height,
    )
    return _view(await _product(product_id))


@gallery_router.delete("/products/{product_id}/gallery/images/{image_id}")
async def delete_gallery_image(
    product_id: str,
    image_id: str,
    body: GalleryDelete,
    current=Depends(require("products.edit")),
):
    product = await _product(product_id)
    revision = int(product.get("gallery_revision") or 0)
    if body.expected_revision != revision:
        raise HTTPException(
            status_code=409, detail="The photo gallery changed. Reload and try again."
        )
    before = _items(product)
    target = next((item for item in before if item["id"] == image_id), None)
    stored_target = next(
        (
            item
            for item in _db_images(product)
            if (item.get("id") or gc.stable_id(item["image_url"])) == image_id
        ),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="Image not found.")
    if (
        target.get("source") != "r2"
        or not stored_target
        or not stored_target.get("object_key")
    ):
        raise HTTPException(
            status_code=400, detail="Approved catalogue photos cannot be deleted here."
        )
    new = [item for item in before if item["id"] != image_id]
    at = now_iso()
    result = await db.products.update_one(
        {"id": product_id, "gallery_revision": revision},
        {
            "$set": {
                "images": _stored_images(new, product),
                "gallery_order": [item["url"] for item in new],
                "gallery_revision": revision + 1,
                "gallery_updated_at": at,
                "updated_at": at,
            }
        },
    )
    if result.modified_count != 1:
        raise HTTPException(
            status_code=409, detail="The photo gallery changed. Reload and try again."
        )
    warning = None
    try:
        await asyncio.to_thread(_delete_r2, stored_target["object_key"])
    except Exception as error:
        logger.exception(
            "R2 cleanup failed for %s: %s",
            stored_target["object_key"],
            type(error).__name__,
        )
        warning = "The image was removed from the product, but storage cleanup needs attention."
    await _audit(
        product,
        current,
        "delete",
        before,
        new,
        revision + 1,
        image_id=image_id,
        object_key=stored_target["object_key"],
        cleanup_warning=warning,
    )
    view = _view(await _product(product_id))
    if warning:
        view["warning"] = warning
    return view


@gallery_router.get("/products/{product_id}/gallery/history")
async def gallery_history(product_id: str, current=Depends(require("products.view"))):
    return (
        await db.product_gallery_history.find({"product_id": product_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )


@gallery_router.post("/products/{product_id}/gallery/upload-intent")
async def gallery_upload_intent(
    product_id: str, current=Depends(require("products.edit"))
):
    await _product(product_id)
    status = uploads_status()
    if not status["enabled"]:
        raise HTTPException(
            status_code=503, detail=status["reason"] + " " + status["setup"]
        )
    return {
        "enabled": True,
        "max_images": MAX_PRODUCT_IMAGES,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "accepted_types": ["image/jpeg", "image/png", "image/webp"],
    }
