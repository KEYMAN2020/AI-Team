"""错误码定义 — 统一错误码常量

规范：
- 0：成功
- 1xxxx：业务错误
- 2xxxx：权限/认证错误
- 3xxxx：参数校验错误
- 5xxxx：系统错误
"""

# ── 成功 ──
SUCCESS = 0

# ── 业务错误 (1xxxx) ──
USER_NOT_FOUND = 10001
USER_ALREADY_EXISTS = 10002
USER_BANNED = 10003
VERIFICATION_CODE_INVALID = 10004
VERIFICATION_CODE_EXPIRED = 10005
VERIFICATION_CODE_TOO_FREQUENT = 10006

# ── 认证/权限错误 (2xxxx) ──
UNAUTHORIZED = 20001
TOKEN_EXPIRED = 20002
TOKEN_INVALID = 20003
FORBIDDEN = 20004

# ── 参数校验错误 (3xxxx) ──
INVALID_PHONE = 30001
MISSING_PARAM = 30002
INVALID_PARAM = 30003
PARAM_TOO_LONG = 30004

# ── 系统错误 (5xxxx) ──
DATABASE_ERROR = 50001
INTERNAL_ERROR = 50002

# 错误码 → 默认消息映射
ERROR_MESSAGES = {
    USER_NOT_FOUND: "用户不存在",
    USER_ALREADY_EXISTS: "用户已存在",
    USER_BANNED: "账号已被封禁",
    VERIFICATION_CODE_INVALID: "验证码错误",
    VERIFICATION_CODE_EXPIRED: "验证码已过期",
    VERIFICATION_CODE_TOO_FREQUENT: "验证码发送过于频繁，请稍后再试",
    UNAUTHORIZED: "未登录或登录已过期",
    TOKEN_EXPIRED: "Token 已过期，请重新登录",
    TOKEN_INVALID: "Token 无效",
    FORBIDDEN: "无权限访问",
    INVALID_PHONE: "手机号格式错误",
    MISSING_PARAM: "缺少必要参数",
    INVALID_PARAM: "参数格式错误",
    PARAM_TOO_LONG: "参数过长",
    DATABASE_ERROR: "数据库异常，请稍后再试",
    INTERNAL_ERROR: "服务器内部错误",
}
