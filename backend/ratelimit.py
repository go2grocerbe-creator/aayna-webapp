"""
Database-backed fixed-window rate limiting.

Serverless deployments run several short-lived instances, so an in-memory
counter (as used by the admin login) can be bypassed by landing on a fresh
instance. These counters live in MongoDB: one document per (scope, subject,
window), incremented atomically. Subjects are hashed so no raw IP or email
address is stored. Old windows are harmless and can be pruned by created_at.
"""
import hashlib
import time

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db, now_iso


def _key(scope: str, subject: str, window: int) -> str:
    bucket = int(time.time() // window)
    digest = hashlib.sha256(f"{scope}|{subject}".encode()).hexdigest()[:32]
    return f"{scope}:{digest}:{bucket}"


async def hit(scope: str, subject: str, limit: int, window: int) -> int:
    """Count one event and return the count in the current window."""
    doc = await db.rate_limits.find_one_and_update(
        {"_id": _key(scope, subject, window)},
        {"$inc": {"count": 1}, "$setOnInsert": {"scope": scope, "created_at": now_iso()}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return int(doc.get("count", 1))


async def enforce(scope: str, subject: str, limit: int, window: int,
                  message: str = "Too many attempts. Please wait a few minutes and try again."):
    """Count one event; raise 429 once the window's limit is exceeded."""
    if await hit(scope, subject, limit, window) > limit:
        raise HTTPException(status_code=429, detail=message)


async def exceeded(scope: str, subject: str, limit: int, window: int) -> bool:
    """Count one event; return True (without raising) when over the limit.
    Used where the public response must stay identical (no enumeration)."""
    return await hit(scope, subject, limit, window) > limit


async def count(scope: str, subject: str, window: int) -> int:
    doc = await db.rate_limits.find_one({"_id": _key(scope, subject, window)})
    return int((doc or {}).get("count", 0))


async def reset(scope: str, subject: str, window: int):
    await db.rate_limits.delete_one({"_id": _key(scope, subject, window)})
