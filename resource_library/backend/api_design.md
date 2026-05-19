# 后端 API 设计规范

## 统一响应格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": {},
  "request_id": "uuid"
}
```
错误时 code 为非零，msg 为用户友好错误描述，data 可附错误详情。

## 错误码设计
- 1xxxx：业务错误（如 10001 用户不存在）
- 2xxxx：权限错误（如 20001 未登录）
- 3xxxx：参数错误（如 30001 参数缺失）
- 5xxxx：系统错误（如 50001 数据库异常）

## RESTful 命名规范
- 资源复数：/users, /orders, /products
- 嵌套资源：/users/{id}/orders（不超过两层）
- 动作用动词前缀：POST /users/{id}/activate（非 CRUD 操作）

## 参数校验
- 必须在 Controller 层做完整校验，不能让非法参数进入 Service
- 使用 Pydantic (Python) / Zod (TS) / Jakarta Validation (Java)
- 校验失败统一返回 400，body 包含具体字段错误

## 分页规范
```json
{"data": [], "total": 100, "page": 1, "page_size": 20, "has_more": true}
```

## 幂等性
- POST 创建资源：客户端传 idempotency_key，服务端 Redis 去重
- 支付、发券等高风险操作必须实现幂等
