# 架构设计原则

## SOLID 原则
- **S** 单一职责：每个模块只做一件事
- **O** 开闭原则：对扩展开放，对修改关闭
- **L** 里氏替换：子类可替换父类
- **I** 接口隔离：细粒度接口优于大而全
- **D** 依赖倒置：依赖抽象而非具体实现

## 常用架构模式
- **分层架构**：Controller → Service → Repository → DB（清晰边界，易于测试）
- **CQRS**：读写分离，Command 写数据，Query 读数据（高并发场景）
- **事件驱动**：通过事件解耦组件（适合异步处理、审计日志）
- **微服务**：按业务域拆分服务（适合团队独立发布需求）

## API 设计原则
- REST: 资源导向，使用 HTTP 动词（GET/POST/PUT/PATCH/DELETE）
- 版本化：URL 前缀 /api/v1 或 Header Accept-Version
- 分页：cursor-based 优于 offset（大数据量时性能更好）
- 幂等性：PUT/DELETE 必须幂等；POST 通过 idempotency-key 实现

## 系统设计要点
- 单点故障（SPOF）：识别并消除关键路径上的单点
- 水平扩展：无状态设计，Session 存 Redis
- 缓存策略：Cache-Aside / Write-Through / Write-Behind 按场景选择
- 限流熔断：令牌桶/漏桶限流，Circuit Breaker 防雪崩
