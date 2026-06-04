"""统一响应格式

所有 API 返回：
{"code": 0, "data": {...}, "message": "ok"}
"""

from flask import jsonify


class ApiError(Exception):
    """业务异常"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def to_response(self):
        return jsonify({
            "code": self.status_code,
            "data": None,
            "message": self.message
        }), self.status_code


def success(data=None, message="ok"):
    return jsonify({"code": 0, "data": data, "message": message})


def error(message: str, status_code: int = 400):
    return jsonify({
        "code": status_code,
        "data": None,
        "message": message
    }), status_code
