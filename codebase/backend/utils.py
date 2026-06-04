"""工具函数：手机号校验、验证码"""

import random
import re
import threading
from datetime import datetime, timedelta


def is_valid_phone(phone: str) -> bool:
    """校验中国大陆手机号格式"""
    return bool(re.match(r"^1[3-9]\d{9}$", phone))


# ── 验证码（内存存储，生产环境应替换为 Redis） ────────

_verify_store: dict = {}
_store_lock = threading.Lock()


def _clean_expired():
    now = datetime.now()
    expired = [k for k, v in _verify_store.items() if v["expires_at"] < now]
    for k in expired:
        del _verify_store[k]


def generate_verification_code(phone: str, purpose: str = "login") -> str:
    """生成验证码（Mock 实现，仅打印到控制台）"""
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.now() + timedelta(seconds=300)

    key = f"{phone}:{purpose}"
    with _store_lock:
        _clean_expired()
        _verify_store[key] = {"code": code, "expires_at": expires_at}

    print(f"[Mock SMS] phone={phone}, purpose={purpose}, "
          f"code={code}, expires_at={expires_at.isoformat()}Z")
    return code


def verify_code(phone: str, code: str, purpose: str = "login") -> bool:
    """校验验证码（一次性）"""
    key = f"{phone}:{purpose}"
    with _store_lock:
        record = _verify_store.get(key)
        if not record:
            return False
        if record["expires_at"] < datetime.now():
            del _verify_store[key]
            return False
        if record["code"] != code:
            return False
        del _verify_store[key]
        return True
