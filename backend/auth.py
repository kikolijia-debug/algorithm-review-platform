"""轻量账号体系：PBKDF2 口令散列 + 会话令牌。

会话存在 SQLite 里而不是进程内存中，这样重启服务（部署更新、服务器重启）
不会把所有人踢下线。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

SESSION_TTL = 60 * 60 * 24 * 7  # 7 天


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 60_000)
    return dk.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    calc, _ = hash_password(password, salt)
    return hmac.compare_digest(calc, hashed)


def create_session(user: dict) -> str:
    from . import db

    token = secrets.token_urlsafe(32)
    db.ex(
        "INSERT OR REPLACE INTO sessions(token,user_id,role,name,issued) VALUES(?,?,?,?,?)",
        (token, user["id"], user["role"], user["name"], time.time()),
    )
    return token


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    from . import db

    row = db.q1("SELECT * FROM sessions WHERE token=?", (token,))
    if not row:
        return None
    if time.time() - row["issued"] > SESSION_TTL:
        db.ex("DELETE FROM sessions WHERE token=?", (token,))
        return None
    user = db.q1("SELECT id,username,role,name,class_name FROM users WHERE id=?", (row["user_id"],))
    if not user:
        db.ex("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return {
        "id": user["id"],
        "user_id": user["id"],
        "role": user["role"],
        "name": user["name"],
        "username": user["username"],
        "class_name": user["class_name"],
        "issued": row["issued"],
    }


def drop_session(token: str | None) -> None:
    if token:
        from . import db

        db.ex("DELETE FROM sessions WHERE token=?", (token,))
