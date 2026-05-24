# DevOps Baseline（n8n_0523_2114）

## 1) 项目技术栈分析（初始化假设）
当前为项目初始化阶段，尚无历史任务与明确后端依赖清单。基于任务目标（环境与部署基线草案）采用**通用容器化后端服务基线**：
- 运行时：Linux + Docker Engine
- 编排：docker compose（dev/staging 基线），prod 可平滑迁移 K8s
- CI/CD：GitHub Actions（可等价迁移 GitLab CI/Jenkins）
- 配置管理：`.env` 分层 + CI Secret + 生产密钥托管（Vault/云 KMS）
- 可观测性：应用健康检查 + 容器日志标准输出 + 指标抓取预留

> 待后端给出实际语言栈（Node/Python/Java）后，仅需替换 Dockerfile 构建段，不影响整体基线结构。

---

## 2) 环境基线（dev / staging / prod）

### dev（开发环境）
- 目标：快速迭代、联调、可调试
- 特性：
  - 本地 compose 启动
  - 挂载源码（可选）
  - 使用 `.env.dev` 非敏感配置
  - 允许较详细日志级别（DEBUG/INFO）

### staging（预发布环境）
- 目标：发布前验证（功能、性能冒烟、迁移验证）
- 特性：
  - 与 prod 尽量同构（镜像、网络、入口）
  - 使用 `.env.staging` + CI Secret
  - 仅允许受控测试数据
  - 开启健康检查和基础告警

### prod（生产环境）
- 目标：高可用、稳定、可回滚、可审计
- 特性：
  - 仅通过 CI/CD 部署，不允许手工改容器
  - Secret 从密钥管理系统注入（Vault/KMS/Secrets Manager）
  - 最小权限运行（非 root、只读文件系统可选）
  - 监控告警与日志留存策略生效

---

## 3) 配置分离策略

### 配置层级
1. **代码内默认值**：仅本地无害默认值
2. **环境文件**：`.env.dev` / `.env.staging` / `.env.prod`（prod 不入库）
3. **CI/CD Secret**：注入敏感信息（DB 密码、Token）
4. **运行时密钥服务**：生产密钥动态获取与轮转

### 原则
- 严禁将真实密钥提交到 Git
- 非敏感配置可版本化（如 FEATURE_FLAG）
- 敏感配置统一由 Secret 管理系统维护
- 配置变更走 PR + 审计

---

## 4) 容器化基线

### 镜像构建要求
- 多阶段构建（减少镜像体积）
- 固定基础镜像大版本（如 node:20-alpine）
- 以非 root 用户运行
- 镜像打标签：`app:<git-sha>` 与 `app:semver`

### 运行要求
- `restart: unless-stopped`（dev/staging）/ 编排器重启策略（prod）
- 健康检查（HTTP `/healthz` 或 TCP）
- 日志输出 stdout/stderr，禁止写容器本地文件
- 资源限制（CPU/MEM）按环境配置

---

## 5) CI/CD 阶段定义（建议）

### CI（每次 PR / push）
1. **lint**：代码规范检查
2. **test**：单元测试
3. **build**：构建镜像
4. **scan**：依赖/镜像漏洞扫描（Trivy/Snyk）
5. **artifact**：推送镜像到镜像仓库（仅主干）

### CD（分环境）
- **deploy-dev**：自动（主干合并触发）
- **deploy-staging**：自动或半自动（需审批）
- **deploy-prod**：手动审批 + 变更窗口

### 发布策略
- 默认 **Rolling Update**
- 关键版本支持 **Blue/Green** 或 **Canary**（后续按业务流量规模引入）

---

## 6) 服务发现、健康检查、日志与监控告警基线

### 服务发现
- compose：服务名 DNS（如 `app`, `db`, `redis`）
- prod：通过 K8s Service / 云内网 DNS

### 健康检查
- 存活检查（liveness）：进程是否存活
- 就绪检查（readiness）：依赖（DB/Cache）是否可用
- 失败阈值建议：连续 3 次失败判定异常

### 日志采集
- 应用结构化日志（JSON）
- 容器日志采集到集中平台（ELK/Loki/Cloud Logging）
- 保留与脱敏策略：PII 脱敏、错误日志>=30天（按合规调整）

### 监控告警
- 指标：QPS、错误率、P95 延迟、容器重启次数、CPU/MEM、磁盘
- 告警：
  - 5xx 错误率连续 5 分钟超阈值
  - P95 延迟超阈值
  - 实例不可用/重启风暴
- 通知：企业 IM + 邮件 + 值班系统

---

## 7) 基线配置文件模板（草案）

> 以下模板用于快速落地，待后端语言确定后替换构建命令。

### Dockerfile（通用占位）
```dockerfile
FROM alpine:3.20
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY . /app
USER app
EXPOSE 8080
CMD ["sh", "-c", "echo 'replace with real startup command' && sleep infinity"]
```

### docker-compose.yml（dev/staging 基线）
```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: n8n_0523_2114/app:dev
    env_file:
      - .env.dev
    ports:
      - "8080:8080"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "sh", "-c", "wget -qO- http://127.0.0.1:8080/healthz || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### CI（GitHub Actions）
```yaml
name: ci-cd
on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t app:${{ github.sha }} .

  deploy-dev:
    if: github.ref == 'refs/heads/main'
    needs: ci
    runs-on: ubuntu-latest
    steps:
      - name: Deploy placeholder
        run: echo "deploy to dev"
```

---

## 8) 环境变量清单（初版）

| 变量名 | 说明 | 示例值 | 敏感 |
|---|---|---|---|
| APP_ENV | 运行环境 | dev/staging/prod | 否 |
| APP_PORT | 服务端口 | 8080 | 否 |
| LOG_LEVEL | 日志级别 | info | 否 |
| DATABASE_URL | 数据库连接串 | postgresql://user:***@db:5432/app | 是 |
| REDIS_URL | 缓存连接串 | redis://redis:6379/0 | 是 |
| JWT_SECRET | 认证签名密钥 | \*\*\* | 是 |
| API_KEY_xxx | 第三方 API 密钥 | \*\*\* | 是 |
| OTEL_EXPORTER_OTLP_ENDPOINT | 观测上报端点 | http://otel-collector:4317 | 否 |

---

## 9) 部署步骤（基线）
1. 准备环境变量文件（dev/staging）和 Secret（prod）。
2. 本地验证：`docker compose --env-file .env.dev up -d --build`。
3. 提交代码触发 CI（lint/test/build/scan）。
4. 主干合并自动部署 dev；staging/prod 按审批流发布。
5. 发布后检查健康接口、核心业务冒烟、关键指标告警状态。

---

## 10) 回滚方案（基线）
- **镜像级回滚**：保留最近 N 个稳定镜像 tag，故障时回滚到 `last-known-good`。
- **配置级回滚**：环境变量采用版本化管理，支持恢复到上一版。
- **数据库变更**：迁移必须可逆（up/down）；生产先做备份。
- **执行流程**：
  1) 停止当前发布批次；2) 切回稳定镜像；3) 验证健康检查与关键路径；4) 复盘并补充防回归测试。

---

## 11) 后续待补齐项（给后端/架构）
- 明确后端语言栈与启动命令
- 明确数据库、中间件清单
- 明确云平台（AWS/Azure/GCP/自托管）
- 明确 SLA/SLO 与告警阈值
