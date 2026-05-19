# 错误处理最佳实践

## 错误分层
- **已知业务错误**：抛自定义异常（BusinessException），包含错误码和描述
- **参数错误**：校验框架自动处理，统一 400 响应
- **系统错误**：捕获后记录完整堆栈，返回 500，不暴露内部细节

## 日志规范
```python
# 正确：结构化日志
logger.error("order_failed", order_id=order_id, user_id=user_id, error=str(e))
# 错误：字符串拼接，无法过滤
logger.error(f"error: {e}")
```

## 禁止事项
- 禁止空 except/catch（掩盖错误）
- 禁止在日志中打印密码、token、信用卡号
- 禁止直接将异常信息返回给前端（暴露内部实现）
- 禁止使用 print 替代日志（生产环境无法采集）

## 重试策略
- 网络超时、数据库临时不可用：指数退避重试，最多3次
- 业务逻辑错误（如余额不足）：不重试
- 使用 tenacity (Python) / retry (Go) 等库，不要手写循环
