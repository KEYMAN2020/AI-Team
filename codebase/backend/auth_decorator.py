"""认证装饰器：从 Authorization header 提取并校验 JWT"""

from __future__ import annotations

from functools import wraps

from flask import request

import jwt
from jwt_helper import decode_access_token
from response import ApiError


def require_auth(f):
    """装饰器：要求请求携带有效 Bearer access_token

    校验通过后将 user_id / phone / role 注入 Flask request 对象：
        request.user_id
        request.phone
        request.role
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise ApiError("未提供认证令牌", status_code=401)

        token = auth_header[7:].strip()
        if not token:
            raise ApiError("认证令牌为空", status_code=401)

        try:
            payload = decode_access_token(token)
            if payload.get("type") != "access":
                raise ApiError("令牌类型错误", status_code=401)
        except jwt.ExpiredSignatureError:
            raise ApiError("令牌已过期，请重新登录", status_code=401)
        except jwt.InvalidTokenError:
            raise ApiError("无效的认证令牌", status_code=401)

        request.user_id = payload["user_id"]
        request.phone = payload["phone"]
        request.role = payload["role"]
        return f(*args, **kwargs)

    return decorated
