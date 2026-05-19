# AI-TeaM — 第一次接触使用指南

> AI-TeaM 是一个基于 **Harness 理论** 的 Multi-Agent 软件开发框架。11 个 AI 角色通过 DAG 编排协作，完成从需求分析到代码交付的完整软件研发流程。

---

## 一、这是什么？

简单说：你把一个开发任务丢进来，11 个 AI 角色（PM、产品经理、架构师、UX、DBA、前端、后端、审查员、DevOps、Debug、测试）会自动分工协作，产出完整代码。

```
你："开发一个用户登录注册功能"
  ↓
AI-TeaM Harness（11 角色 DAG 引擎）
  ↓
PM 规划 → Product/UX/Architect/DBA 并行设计 → 人工审批
  → Frontend/Backend/DevOps 并行开发 → Reviewer/Tester 审查测试
  → QA→Debug 自愈循环 → 人工审批发布 → PM 整合交付
  ↓
完整代码 + 测试 + 部署配置 + 文档
```

### 核心概念：客户端无关

Harness（server.py）是独立运行的 HTTP 服务。不管你用什么 AI 客户端，都通过同一个命令触发：

```
Cherry Studio / Codex / Claude Code / 终端 / curl
        │
        ▼
    ait "任务描述"          ← 唯一入口
        │
        ▼
  server.py:8123          ← Harness 引擎
```

---

## 二、环境准备（一次性）

### 1. Python 依赖

```bash
cd D:\RealWork\ai-team
pip install -r requirements.txt

# 至少装一个模型 SDK（当前默认用 DeepSeek，装 openai 即可）
pip install openai
```

### 2. API Key

```bash
# 按你用的模型设置（当前默认 deepseek）
set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# 如果用 Claude
set ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

### 3. 切换模型（可选）

编辑 `config/providers.yaml`：

```yaml
active_provider: deepseek  # deepseek | claude | openai | gemini | any
```

每个 provider 下 11 个角色的模型和 temperature 在 `config/roles.yaml` 独立配置。

---

## 三、第一次使用

### 启动 Harness

```bash
cd D:\RealWork\ai-team
python server.py
```

看到以下输出表示启动成功：

```
╔══════════════════════════════════════════╗
║  AI 开发团队 — HTTP 服务器              ║
║  地址: http://127.0.0.1:8123             ║
╚══════════════════════════════════════════╝
```

### 运行第一个任务

打开新终端：

```bash
cd D:\RealWork\ai-team
python ait "开发一个Todo应用，支持增删改查"
```

### 你会看到的流程

```
[HARNESS] Submitting task to AI-TeaM (11-role DAG)
   Task: 开发一个Todo应用，支持增删改查
   Model: deepseek
============================================================
[OK] Task submitted: task_1712345678

[WAIT] Phase: 第 1 层执行中 | Progress: 15% ...
[WAIT] Phase: 第 2 层执行中 | Progress: 35% ...

⏸  [PAUSE] Human approval needed: 请确认设计方案
     Approve: ait approve
     Reject:  ait reject

[WAIT] Phase: 第 4 层执行中 | Progress: 60% ...

============================================================
Status: done
--- Final Report ---
[PM整合报告：包含前端代码、后端API、数据库Schema、测试用例...]
============================================================
```

---

## 四、核心命令

```bash
# 开发任务
python ait "实现用户登录注册功能，支持JWT"

# 查看项目状态
python ait status

# 审批（遇到审批节点时）
python ait approve
python ait reject

# 健康检查
curl http://localhost:8123/health
```

---

## 五、在不同 AI 客户端中使用

不管你在哪个客户端，都执行同一行命令：

### Cherry Studio（CherryClaw）

内置了 `ai-team-harness` skill，直接说"开发xxx"会自动触发。

### Codex / Claude Code / 任何终端

```bash
python D:\RealWork\ai-team\ait "你的开发任务"
```

### n8n 集成（原始设计路径）

```json
POST http://localhost:8123/run
Body: {"task": "开发xxx", "provider": "deepseek", "project_name": "MyProject"}
```

然后轮询 `GET /status/{task_id}` 直到 `status` 为 `done`。

### 直接 HTTP

```bash
curl -X POST http://localhost:8123/run \
  -H "Content-Type: application/json" \
  -d '{"task":"开发用户系统","provider":"deepseek","project_name":"UserModule"}'
```

---

## 六、角色与执行流程

| 层 | 角色 | 并行 | 产出 |
|----|------|------|------|
| 1 | PM | 串行 | DAG 执行计划 |
| 2 | Product + UX + Architect + DBA | 3 并行 | 需求文档、UX设计、架构方案、DB Schema |
| ⏸ | 人工审批点1 | - | 确认设计 |
| 3 | Frontend + Backend + DevOps | 3 并行 | 前端代码、后端API、CI/CD配置 |
| 4 | Reviewer + Tester | 2 并行 | 代码审查报告、测试报告 |
| 🔁 | QA→Debug→QA 循环 | 串行 | Bug修复（最多3轮）
| ⏸ | 人工审批点2 | - | 发布确认 |
| 5 | PM | 串行 | 最终交付报告 |

每个角色使用独立配置的模型，例如 PM 和架构师用 `deepseek-v4-pro + thinking=true`，UI 用 `deepseek-v4-flash`。

---

## 七、核心配置

| 文件 | 作用 |
|------|------|
| `config/providers.yaml` | 模型提供商 + active_provider |
| `config/roles.yaml` | 每个角色在每种 provider 下的模型、温度、超时 |
| `config/workflow.yaml` | DAG 参数：重试次数、超时、QA循环上限、自动审批 |
| `references/roles/*/config.yaml` | 角色基础配置 |
| `references/roles/*/prompt.md` | 角色系统提示词 |

### 开启自动审批（跳过人工节点）

编辑 `config/workflow.yaml`：

```yaml
auto_approve: true
```

---

## 八、加新角色

只需创建目录，不用改任何 `.py` 文件：

```bash
mkdir references/roles/security
```

放入两个文件：
- `config.yaml` — 角色配置（模型、温度等）
- `prompt.md` — 系统提示词

重启 server.py 即可生效。

---

## 九、故障排查

### server.py 启动失败

```bash
# 检查依赖
python -c "import yaml, openai; print('OK')"

# 检查端口占用
netstat -ano | findstr 8123
```

### 任务失败

```bash
# 查看项目状态
python -c "from references.state_manager import get_project; print(get_project())"

# 从快照回滚
python -c "from references.state_manager import rollback_to_snap; rollback_to_snap('last')"

# 调试模式
python references/debugger.py health
python references/debugger.py dry_run "你的任务"
```

### Windows 编码问题

`ait` 已内置 UTF-8 强制输出，无需额外处理。如果直接在 PowerShell 跑 server.py 有乱码：

```powershell
chcp 65001
python server.py
```
