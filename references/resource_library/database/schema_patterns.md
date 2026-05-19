# 数据库设计模式

## 表设计规范
- 必备字段：id (BIGSERIAL PK), created_at, updated_at（用 trigger 自动更新）
- 软删除：is_deleted BOOLEAN DEFAULT FALSE + deleted_at（审计需要）
- 外键约束：显式声明 FOREIGN KEY，不要只靠代码保证
- 命名：表名复数 snake_case，字段 snake_case，外键 {table}_id

## 索引策略
- 主键自带索引，无需重复创建
- 高频 WHERE 字段加索引：状态字段、外键字段、时间范围查询字段
- 联合索引：最左前缀原则，把区分度高的字段放左边
- 避免在低区分度字段建索引（如 gender, is_active）
- EXPLAIN ANALYZE 验证索引是否被使用

## 常见性能陷阱
- N+1 查询：ORM 关联查询必须用 JOIN 或 prefetch_related
- 全表扫描：WHERE 子句确保命中索引
- 大事务：事务尽量小，避免长时间锁表
- SELECT *：只查需要的字段，大表尤其注意

## Migration 规范
- 每次变更一个独立 migration 文件，包含 up 和 down
- 生产环境先在测试环境验证
- 添加列：可热更新；删除列：先废弃再删除（两步发布）
- 大表加索引：使用 CONCURRENTLY 避免锁表

## 事务使用
- 跨表操作必须用事务
- 事务边界在 Service 层，不在 Repository 层
- 读操作不需要事务（除非需要一致性读）
