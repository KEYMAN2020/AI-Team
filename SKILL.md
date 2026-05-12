# AI 开发团队

Multi-Agent 软件开发框架，11 个专业角色并行协作。专为 Cherry Studio → n8n → Claude API 架构设计。

## 架构

```
Cherry Studio（人类 I/O 界面）
       │  用户输入需求
       ▼
n8n（工作流编排）
       │  POST /run + webhook 回调
       ▼
server.py（HTTP API, port 8123）
       │
       ├─ PM 规划 DAG
       ├─ 各角色并行调用 LLM（异步执行）
       ├─ 人工审批节点等待（POST /approve）
       └─ 结果回调 n8n webhook
```

## 团队成员（11 个角色）

| 代号 | 角色 | 核心职责 |
|------|------|---------|
| PM | Tech Lead | DAG 规划、进度协调、最终整合 |
| Product | 产品经理 | 需求澄清、用户故事、验收标准 |
| Architect | 架构师 | 系统设计、接口约定、技术选型 |
| UX | UX 设计师 | 用户旅程、页面规格、交互设计 |
| DBA | 数据库管理员 | Schema 设计、Migration、查询优化 |
| Frontend | 前端开发 | UI 实现、单元测试 |
| Backend | 后端开发 | API 实现、业务逻辑、单元测试 |
| Reviewer | 代码审查员 | 代码质量、规范符合度、安全基础 |
| DevOps | DevOps | 部署配置、CI/CD |
| Debug | Debug 工程师 | 根因分析、Bug 修复 |
| Tester | 测试工程师 | 集成测试、验收测试、质量结论 |

## 目录结构

```
ai-team/
├── server.py                  # n8n HTTP 入口（核心入口）
├── SKILL.md                   # 本文档
├── requirements.txt           # Python 依赖
├── references/
│   ├── runner.py              DAG 执行引擎
│   ├── message_bus.py         Agent 间消息总线
│   ├── model_adapter.py       模型适配层（切换 LLM）
│   ├── state_manager.py       状态管理 + 快照 + 回滚
│   ├── knowledge_base.py      项目知识库
│   ├── tools_registry.py      工具注册表
│   ├── resource_library.py    技术知识储备库
│   ├── doc_generator.py       API 文档生成
│   ├── debugger.py            调试工具
│   └── roles/                 11 个角色的系统提示词
│       ├── pm.md / product.md / architect.md / ux.md
│       ├── dba.md / frontend.md / backend.md
│       ├── reviewer.md / devops.md / debug.md / tester.md
├── knowledge/                 项目知识库
│   ├── decisions.md           ADR
│   ├── standards.md           编码规范
│   ├── gotchas.md             已知坑
│   ├── glossary.md            词汇表
│   └── postmortems.md         故障复盘
├── state/
│   ├── master.json            统一状态文件
│   └── snapshots/             快照（自动备份）
└── logs/
    └── dispatch_log.jsonl     调度日志
```

## 快速启动

### 1. 安装依赖

```bash
cd ai-team
pip install -r requirements.txt

# 至少装一个模型 SDK
pip install anthropic      # Claude
pip install openai          # DeepSeek / OpenAI
pip install google-genai    # Gemini
```

### 2. 设置 API Key

```bash
# 按需设置
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
export OPENAI_API_KEY="sk-..."
```

### 3. 切换模型

编辑 `references/model_adapter.py`：

```python
ACTIVE_PROVIDER = "claude"  # deepseek / claude / openai / gemini / any
```

### 4. 启动服务器

```bash
python server.py
```

默认 `127.0.0.1:8123`。可用环境变量覆盖：
- `AI_TEAM_HOST` — 监听地址
- `AI_TEAM_PORT` — 监听端口

## n8n 集成

### 提交开发任务 — POST /run

| 项目 | 值 |
|------|-----|
| Method | POST |
| URL | `http://localhost:8123/run` |
| Content-Type | `application/json` |

**请求体：**
```json
{
  "task": "实现用户注册登录功能，含 JWT 认证",
  "provider": "claude",
  "project_name": "用户模块",
  "webhook_url": "https://your-n8n/webhook/callback"
}
```

**响应（202 Accepted）：**
```json
{
  "task_id": "task_1712345678",
  "status": "running",
  "message": "任务已提交，请轮询 GET /status/{task_id} 获取结果"
}
```

### 查询状态 — GET /status/{task_id}

```
GET http://localhost:8123/status/task_1712345678
```

**响应：**
```json
{
  "task_id": "task_1712345678",
  "status": "done",
  "task": "...",
  "project": { "name": "用户模块", "progress": 100, ... },
  "result": "最终交付报告..."
}
```

轮询方式：n8n 使用 **Wait** 节点 + **HTTP Request** 节点循环查询直到 status 为 done/error。

### 人工审批 — POST /approve

当 DAG 执行到审批节点时，执行暂停并输出提示。通过此接口响应：

```json
{
  "approved": true,
  "notes": "方案没问题，请继续"
}
```

n8n 集成方式：n8n 工作流监听 server.py 的输出日志，通过 **HTTP Request** 节点调用 POST /approve。

### 项目概览 — GET /status

```
GET http://localhost:8123/status
```

返回项目名称、进度、当前阶段、活跃任务等。

### 健康检查 — GET /health

```
GET http://localhost:8123/health
```

## n8n 工作流示例（Chatflow）

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Chat Trigger │────▶│ HTTP Request │────▶│   Wait 5s     │
│ (用户输入)    │     │ POST /run    │     │               │
└─────────────┘     └──────┬───────┘     └───────┬───────┘
                           │ task_id              │
                           ▼                      ▼
                    ┌──────────────┐     ┌───────────────┐
                    │ HTTP Request │◀────│   Loop: 每 5s │
                    │ GET /status  │     │  直到 done    │
                    └──────┬───────┘     └───────────────┘
                           │ status=done
                           ▼
                    ┌──────────────┐
                    │ 返回结果给    │
                    │ Chat Trigger │
                    └──────────────┘
```

审批分支：
```
┌────────────────┐    ┌──────────────────┐
│ 发现审批暂停     │───▶│ HTTP Request     │
│ (服务器日志)     │    │ POST /approve    │
└────────────────┘    └──────────────────┘
```

## 完整执行流程

```
[PM] 需求分析 + DAG 规划
    │
    ▼
[Product] 需求澄清 → 用户故事 + 验收标准
    │
    ├── [UX] 用户旅程 + 页面规格          ── 并行 ──
    ├── [Architect] 系统架构 + 接口约定
    ├── [DBA] 数据库 Schema + Migration
    │
    ▼
[人工审批1] 确认需求、UX、架构、DB 设计（等待 POST /approve）
    │
    ├── [Frontend] 前端实现 + 单元测试   ── 并行 ──
    ├── [Backend] 后端实现 + 单元测试
    ├── [DevOps] CI/CD 流水线 + 部署配置
    │
    ▼
    ├── [Reviewer] 代码审查          ── 并行 ──
    ├── [Tester] 集成测试 + 验收测试
    │   发现 Bug ──→ [Debug] 根因修复 ──→ [Tester] 回归测试（最多 3 轮）
    │
    ▼
[人工审批2] 发布确认（等待 POST /approve）
    │
    ▼
[PM] 整合所有交付物，输出最终报告
```

## 状态管理

所有状态存储在 `state/master.json`。每次写入自动快照，支持回滚。

```bash
# 查看项目状态
python -c "from references.state_manager import get_project; print(get_project())"

# 初始化新项目
python -c "from references.state_manager import init_project; init_project('我的项目')"

# 列出快照
python -c "from references.state_manager import list_snaps; print(list_snaps())"

# 回滚到上一个快照
python -c "from references.state_manager import rollback_to_snap; rollback_to_snap('last')"
```

## 知识库

各角色自动读取所需知识章节。也可手动操作：

```python
from references.knowledge_base import add_adr, add_gotcha, read_section

add_adr("选择 PostgreSQL", "需要 JSONB", "使用 PG 14+", "运维略复杂")
add_gotcha("JWT 过期未刷新", "用户突然登出", "前端未处理401", "加拦截器")
print(read_section("standards"))
```

## 调试

```bash
python references/debugger.py health
python references/debugger.py trace
python references/debugger.py dry_run "实现登录功能"
```
