import os
import uuid
import logging
import requests
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response

from db import db, now_iso
from auth import get_current_admin

logger = logging.getLogger("aayna.storage")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "aayna"

_storage_key = None

# ---------------------------------------------------------------------------
# Backend selection. Production uses any S3-compatible bucket (Cloudflare R2
# recommended) configured through OBJECT_STORAGE_*. The Emergent object store
# is kept only as a development fallback when those are not set. The bucket
# stays private: images are always served through /api/files/<path> below,
# so stored product URLs never depend on the storage vendor.
# ---------------------------------------------------------------------------
S3_BUCKET = (os.environ.get("OBJECT_STORAGE_BUCKET") or "").strip()
S3_ENDPOINT = (os.environ.get("OBJECT_STORAGE_ENDPOINT") or "").strip()
S3_ACCESS_KEY = (os.environ.get("OBJECT_STORAGE_ACCESS_KEY") or "").strip()
S3_SECRET_KEY = (os.environ.get("OBJECT_STORAGE_SECRET_KEY") or "").strip()
_s3_client = None


def storage_backend() -> str:
    if S3_BUCKET and S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY:
        return "s3"
    if EMERGENT_KEY:
        return "emergent"
    return "none"


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config
        _s3_client = boto3.client(
            "s3", endpoint_url=S3_ENDPOINT, aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY, region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )
    return _s3_client

MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp",
}
ALLOWED_EXT = set(MIME_TYPES.keys())

storage_router = APIRouter(prefix="/api/admin")
files_router = APIRouter(prefix="/api")


def init_storage():
    global _storage_key
    if storage_backend() == "s3":
        _s3()  # build client; object-scoped R2 tokens may not allow HeadBucket
        return "s3"
    if storage_backend() == "none":
        raise RuntimeError("No object storage configured (set OBJECT_STORAGE_* )")
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def init_storage_safe():
    try:
        init_storage()
        logger.info("Object storage initialized (%s)", storage_backend())
    except Exception as exc:  # noqa: BLE001
        logger.error("Storage init failed: %s", exc)


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if storage_backend() == "s3":
        _s3().put_object(Bucket=S3_BUCKET, Key=path, Body=data, ContentType=content_type)
        return {"path": path, "size": len(data)}
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    if resp.status_code == 403:
        # key expired - refresh once
        global _storage_key
        _storage_key = None
        key = init_storage()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    if storage_backend() == "s3":
        obj = _s3().get_object(Bucket=S3_BUCKET, Key=path)
        return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 403:
        global _storage_key
        _storage_key = None
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


@storage_router.post("/upload")
async def upload_image(file: UploadFile = File(...), current=Depends(get_current_admin)):
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF images are allowed")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image must be under 8 MB")
    content_type = MIME_TYPES.get(ext, file.content_type or "application/octet-stream")
    path = f"{APP_NAME}/uploads/{uuid.uuid4().hex}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as exc:  # noqa: BLE001
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=502, detail="Image upload failed. Please try again.")
    stored_path = result.get("path", path)
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "storage_path": stored_path,
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "created_at": now_iso(),
    })
    # Frontend prepends REACT_APP_BACKEND_URL to build a full, public <img> URL.
    return {"path": stored_path, "url_path": f"/api/files/{stored_path}"}


@files_router.get("/files/{path:path}")
async def serve_file(path: str):
    # Only serve objects this app itself uploaded (recorded in db.files) so the
    # public endpoint can't be used to fetch arbitrary keys from the shared
    # object store (M3). Also guards against a bare prefix check being bypassed
    # by path traversal segments.
    if not path.startswith(f"{APP_NAME}/uploads/") or ".." in path.split("/"):
        raise HTTPException(status_code=404, detail="File not found")
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, content_type = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
    media = record.get("content_type") or content_type
    return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=86400"})
