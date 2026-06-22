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

MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp",
}
ALLOWED_EXT = set(MIME_TYPES.keys())

storage_router = APIRouter(prefix="/api/admin")
files_router = APIRouter(prefix="/api")


def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def init_storage_safe():
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as exc:  # noqa: BLE001
        logger.error("Storage init failed: %s", exc)


def put_object(path: str, data: bytes, content_type: str) -> dict:
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
    record = await db.files.find_one({"storage_path": path, "is_deleted": False})
    try:
        data, content_type = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
    media = record.get("content_type") if record else content_type
    return Response(content=data, media_type=media, headers={"Cache-Control": "public, max-age=86400"})
