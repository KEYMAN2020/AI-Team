"""认证模块路由 — 规格表认证模块"""

from flask import Blueprint, request
from response import success, ApiError
from utils import is_valid_phone, generate_verification_code

auth_bp = Blueprint("auth", __name__)


# ═══════════════════════════════════════════════════════
# 1. 发送验证码
# ═══════════════════════════════════════════════════════
@auth_bp.post("/send-code")
def send_code():
    """发送验证码（Mock 版，仅打印到控制台）

    规格表 #1: 向用户手机发送 6 位数字验证码
    ---
    请求: {"phone": "13800138000"}
    响应: {"code": 0, "data": {"expire_in": 300}}
    """
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "")

    if not is_valid_phone(phone):
        raise ApiError("手机号格式错误")

    generate_verification_code(phone, purpose="login")

    return success({"expire_in": 300}, "验证码已发送")
