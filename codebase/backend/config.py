"""应用配置 — 环境变量与常量

所有魔法数字提取为具名常量，通过环境变量覆盖默认值。
"""

from __future__ import annotations

import os

# ── Flask 基础配置 ──
SECRET_KEY: str = os.getenv("SECRET_KEY", "be-enjoying-secret-key-2026")

# ── JWT 配置 ──
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "be-enjoying-jwt-secret-2026")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
    os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
)

# ── MySQL ──
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USER: str = os.getenv("DB_USER", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "Vitality2026!")
DB_NAME: str = os.getenv("DB_NAME", "silver_vitality")
DB_CHARSET: str = "utf8mb4"

# ── 验证码 ──
SMS_CODE_LENGTH: int = 6
SMS_CODE_EXPIRE_SECONDS: int = int(os.getenv("SMS_CODE_EXPIRE_SECONDS", "300"))
SMS_CODE_RESEND_INTERVAL: int = int(os.getenv("SMS_CODE_RESEND_INTERVAL", "60"))

# ── 用户 ──
DEFAULT_NICKNAME_PREFIX: str = "银发会员"
MAX_NICKNAME_LENGTH: int = 50
MAX_BIO_LENGTH: int = 500

# ── Flask ──
JSON_AS_ASCII: bool = False
