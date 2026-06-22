import os
import uuid
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from db import db, now_iso

JWT_ALGORITHM = "HS256"
ACCESS_TTL_DAYS = 7
ADMIN_ROLES = {"super_admin", "admin", "order_manager", "product_manager"}

auth_router = APIRouter(prefix="/api/admin")


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user.get("name"),
        "email": user["email"],
        "role": user["role"],
        "status": user.get("status", "active"),
    }


async def get_current_admin(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user or user.get("status") != "active":
        raise HTTPException(status_code=401, detail="Account not found or inactive")
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    user.pop("password_hash", None)
    return user


class LoginRequest(BaseModel):
    email: str
    password: str


@auth_router.post("/login")
async def login(body: LoginRequest):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") != "active":
        raise HTTPException(status_code=403, detail="This account is inactive")
    token = create_access_token(user)
    return {"token": token, "user": public_user(user)}


@auth_router.get("/me")
async def me(current=Depends(get_current_admin)):
    return public_user(current)


@auth_router.post("/logout")
async def logout(current=Depends(get_current_admin)):
    return {"ok": True}


async def seed_admin():
    email = os.environ.get("ADMIN_LOGIN_EMAIL", "admin@aayna.xyz").strip().lower()
    password = os.environ.get("ADMIN_LOGIN_PASSWORD", "ChangeMe123!")
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "name": "Super Admin",
            "email": email,
            "password_hash": hash_password(password),
            "role": "super_admin",
            "status": "active",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(password), "updated_at": now_iso()}},
        )


async def ensure_indexes():
    try:
        await db.users.create_index("email", unique=True)
        await db.products.create_index("slug")
        await db.orders.create_index("order_number")
        await db.customers.create_index("phone")
    except Exception:
        pass
