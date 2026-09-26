"""轻量账号体系：PBKDF2 口令散列 + 服务端内存会话令牌。"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

SESSIONS: dict[str, dict] = {}
SESSION_TTL = 60 * 60 * 24 * 7  # 7 天


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 60_000)
    return dk.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    return hmac.compare_digest(calc, hashed)


def create_session(user: dict) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "id": user["id"],
        "user_id": user["id"],
        "role": user["role"],
        "name": user["name"],
        "username": user.get("username"),
        "class_name": user.get("class_name"),
        "issued": time.time(),
    }
    return token


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    s = SESSIONS.get(token)
    if not s:
        return None
    if time.time() - s["issued"] > SESSION_TTL:
        SESSIONS.pop(token, None)
        return None
    return s


def drop_session(token: str | None) -> None:
    if token:
        SESSIONS.pop(token, None)
