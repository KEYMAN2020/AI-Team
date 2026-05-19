# DevOps 与部署最佳实践

## 容器化规范
- 使用官方基础镜像（alpine 变体，减小攻击面）
- 多阶段构建（builder + runtime 分离）
- 非 root 用户运行进程
- .dockerignore 排除 node_modules、.env、.git

## 环境变量管理
- 开发：.env 文件（不进代码库，用 .env.example 做模板）
- 生产：Secret Manager（AWS Secrets Manager / Vault / K8s Secret）
- 不同环境用不同配置，代码不做环境判断

## CI/CD 流水线阶段
1. Lint + 格式检查
2. 单元测试
3. 构建（Docker image）
4. 集成测试
5. 安全扫描（依赖漏洞、镜像扫描）
6. 部署到 Staging
7. E2E 测试
8. 人工确认 → 部署到生产

## 部署策略
- 蓝绿部署：零停机，快速回滚（维护两套环境）
- 滚动更新：逐步替换，节省资源
- 金丝雀发布：先给 5% 流量，观察后全量

## 健康检查
- Liveness probe：进程是否存活（失败则重启容器）
- Readiness probe：是否准备好接流量（失败则从负载均衡摘除）
- Startup probe：慢启动应用的初始化等待

## 日志与监控
- 结构化日志输出到 stdout（容器化标准）
- 关键指标：错误率、P50/P99 延迟、QPS、饱和度
- 告警阈值：错误率 > 1%、P99 > 2s、磁盘 > 80%
