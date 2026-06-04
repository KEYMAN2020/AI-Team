"""JWT 工具函数：access_token / refresh_token 生成与校验"""

from __future__ import annotations

import secrets
import time
import jwt

from config import Config

ACCESS_TOKEN_EXPIRE = 1800       # 30 分钟
REFRESH_TOKEN_EXPIRE = 604800   # 7 天
ALGORITHM = "HS256"


def generate_access_token(user_id: int, phone: str, role: str) -> str:
    """生成短期 access_token"""
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "phone": phone,
        "role": role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE,
        "jti": secrets.token_hex(16),
        "type": "access",
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """校验并解码 access_token，失败抛出异常"""
    return jwt.decode(
        token,
        Config.JWT_SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "user_id", "type"]},
    )


def generate_refresh_token_str() -> str:
    """生成随机 refresh_token 字符串"""
    return secrets.token_urlsafe(64)
