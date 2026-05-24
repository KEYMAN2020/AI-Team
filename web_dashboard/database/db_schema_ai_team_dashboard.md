# AI Team Dashboard 数据库 Schema 与 Migration 设计

## 1. 设计目标
基于当前已确认的 MVP 需求（团队总览、成员与角色分布、任务状态概览、静态 HTML 展示），设计一套可支持后续数据化演进的关系型数据库结构。

目标：
- 支持 `team` 维度的仪表盘展示
- 支持团队成员、角色、成员状态管理
- 支持任务及任务状态统计
- 预留软删除与审计字段
- 提供可执行的 PostgreSQL migration 示例

> 说明：虽然当前产品范围声明“本次不包含后端接口定义与数据库设计”，但为了后续前后端演进与数据接入，先行设计最小可扩展 schema 是合理的架构准备动作。

---

## 2. 设计假设
由于原始需求信息有限，以下为当前 schema 的明确假设：

1. **ai-team** 当前按“一个或多个团队”的概念建模，而不是写死为单团队。
2. 仪表盘主要围绕：
   - 团队
   - 成员
   - 角色
   - 任务
3. 一个成员可属于一个团队；若未来存在跨团队场景，可扩展为多对多。
4. 一个成员可承担一个主角色；如未来需要多角色，可扩展成员-角色关联表。
5. 一个任务归属于一个团队，并可分配给一个成员。
6. 当前 MVP 只需要任务状态摘要，不需要子任务、评论、附件、工时等复杂能力。
7. 数据库使用 **PostgreSQL**。

---

## 3. 核心实体

### 3.1 teams
用于存储仪表盘中的团队信息。

关键字段：
- `name`：团队名称
- `code`：团队唯一编码，便于程序引用
- `description`：团队说明
- `status`：团队状态，如 active/inactive/archived

### 3.2 roles
用于存储角色定义，如 PM、Frontend、Backend、Designer、AI Agent 等。

关键字段：
- `name`：角色名称
- `code`：角色唯一编码
- `description`：角色说明

### 3.3 members
用于存储团队成员。

关键字段：
- `team_id`：成员所属团队
- `role_id`：成员主角色
- `name`：成员姓名/显示名
- `email`：联系邮箱，可为空
- `avatar_url`：头像地址，可为空
- `member_status`：成员状态，如 active/busy/offline/inactive

### 3.4 tasks
用于存储团队任务或项目工作项。

关键字段：
- `team_id`：所属团队
- `assignee_member_id`：负责人
- `title`：任务标题
- `description`：任务描述
- `task_status`：任务状态，如 todo/in_progress/done/blocked
- `priority`：优先级，如 low/medium/high/critical
- `due_date`：截止日期

---

## 4. 表结构设计

### 4.1 通用字段规范
依据项目知识库中的 schema 规范，每张核心业务表包含：
- `id BIGSERIAL PRIMARY KEY`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
- `deleted_at TIMESTAMPTZ NULL`

同时使用 trigger 自动维护 `updated_at`。

---

### 4.2 teams

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGSERIAL | PK | 主键 |
| code | VARCHAR(64) | NOT NULL, UNIQUE | 团队编码 |
| name | VARCHAR(128) | NOT NULL | 团队名称 |
| description | TEXT | NULL | 描述 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'active' | 团队状态 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间 |
| is_deleted | BOOLEAN | NOT NULL DEFAULT FALSE | 软删除标记 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |

建议约束：
- `CHECK (status IN ('active', 'inactive', 'archived'))`

---

### 4.3 roles

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGSERIAL | PK | 主键 |
| code | VARCHAR(64) | NOT NULL, UNIQUE | 角色编码 |
| name | VARCHAR(128) | NOT NULL | 角色名称 |
| description | TEXT | NULL | 描述 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间 |
| is_deleted | BOOLEAN | NOT NULL DEFAULT FALSE | 软删除标记 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |

备注：
- 当前角色作为全局字典表，不按团队隔离。

---

### 4.4 members

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGSERIAL | PK | 主键 |
| team_id | BIGINT | NOT NULL, FK -> teams(id) | 所属团队 |
| role_id | BIGINT | NOT NULL, FK -> roles(id) | 主角色 |
| name | VARCHAR(128) | NOT NULL | 成员名称 |
| email | VARCHAR(255) | NULL | 邮箱 |
| avatar_url | TEXT | NULL | 头像地址 |
| member_status | VARCHAR(32) | NOT NULL DEFAULT 'active' | 成员状态 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间 |
| is_deleted | BOOLEAN | NOT NULL DEFAULT FALSE | 软删除标记 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |

建议约束：
- `CHECK (member_status IN ('active', 'busy', 'offline', 'inactive'))`
- 可选唯一约束：`UNIQUE(team_id, email)`，但需要允许 `NULL`

说明：
- 当前模型中成员只属于一个团队。
- 若后续需要“一个成员属于多个团队”，可拆为 `members` + `team_members`。

---

### 4.5 tasks

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGSERIAL | PK | 主键 |
| team_id | BIGINT | NOT NULL, FK -> teams(id) | 所属团队 |
| assignee_member_id | BIGINT | NULL, FK -> members(id) | 负责人 |
| title | VARCHAR(255) | NOT NULL | 任务标题 |
| description | TEXT | NULL | 任务描述 |
| task_status | VARCHAR(32) | NOT NULL DEFAULT 'todo' | 任务状态 |
| priority | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 优先级 |
| due_date | DATE | NULL | 截止日期 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间 |
| is_deleted | BOOLEAN | NOT NULL DEFAULT FALSE | 软删除标记 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |

建议约束：
- `CHECK (task_status IN ('todo', 'in_progress', 'done', 'blocked'))`
- `CHECK (priority IN ('low', 'medium', 'high', 'critical'))`

说明：
- `assignee_member_id` 允许为空，以支持未分配任务。
- 当前任务只支持单负责人。

---

## 5. ER 关系说明

```text
teams 1 ──── * members
roles 1 ──── * members
teams 1 ──── * tasks
members 1 ──── * tasks   (via assignee_member_id, nullable)
```

业务含义：
- 一个团队有多个成员
- 一个角色可被多个成员使用
- 一个团队有多个任务
- 一个成员可以负责多个任务

---

## 6. 推荐索引设计

为支持仪表盘常见查询，建议增加如下索引：

### teams
- `uq_teams_code(code)` 唯一索引

### roles
- `uq_roles_code(code)` 唯一索引

### members
- `idx_members_team_id(team_id)`
- `idx_members_role_id(role_id)`
- `idx_members_status(member_status)`
- `idx_members_team_status(team_id, member_status)`
- 可选：`uq_members_team_email(team_id, email) WHERE email IS NOT NULL AND is_deleted = FALSE`

### tasks
- `idx_tasks_team_id(team_id)`
- `idx_tasks_assignee_member_id(assignee_member_id)`
- `idx_tasks_status(task_status)`
- `idx_tasks_team_status(team_id, task_status)`
- `idx_tasks_due_date(due_date)`

这些索引可优化：
- 团队成员列表查询
- 角色分布统计
- 任务状态聚合统计
- 团队看板按状态筛选

---

## 7. PostgreSQL Migration 示例

以下为建议的初始 migration：

```sql
-- 0001_init_ai_team_dashboard.sql

BEGIN;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE teams (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ NULL,
  CONSTRAINT chk_teams_status CHECK (status IN ('active', 'inactive', 'archived'))
);

CREATE TABLE roles (
  id BIGSERIAL PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE members (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL,
  role_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  email VARCHAR(255),
  avatar_url TEXT,
  member_status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ NULL,
  CONSTRAINT fk_members_team_id FOREIGN KEY (team_id) REFERENCES teams(id),
  CONSTRAINT fk_members_role_id FOREIGN KEY (role_id) REFERENCES roles(id),
  CONSTRAINT chk_members_status CHECK (member_status IN ('active', 'busy', 'offline', 'inactive'))
);

CREATE TABLE tasks (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL,
  assignee_member_id BIGINT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  task_status VARCHAR(32) NOT NULL DEFAULT 'todo',
  priority VARCHAR(32) NOT NULL DEFAULT 'medium',
  due_date DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ NULL,
  CONSTRAINT fk_tasks_team_id FOREIGN KEY (team_id) REFERENCES teams(id),
  CONSTRAINT fk_tasks_assignee_member_id FOREIGN KEY (assignee_member_id) REFERENCES members(id),
  CONSTRAINT chk_tasks_status CHECK (task_status IN ('todo', 'in_progress', 'done', 'blocked')),
  CONSTRAINT chk_tasks_priority CHECK (priority IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX idx_members_team_id ON members(team_id);
CREATE INDEX idx_members_role_id ON members(role_id);
CREATE INDEX idx_members_status ON members(member_status);
CREATE INDEX idx_members_team_status ON members(team_id, member_status);

CREATE UNIQUE INDEX uq_members_team_email_active
  ON members(team_id, email)
  WHERE email IS NOT NULL AND is_deleted = FALSE;

CREATE INDEX idx_tasks_team_id ON tasks(team_id);
CREATE INDEX idx_tasks_assignee_member_id ON tasks(assignee_member_id);
CREATE INDEX idx_tasks_status ON tasks(task_status);
CREATE INDEX idx_tasks_team_status ON tasks(team_id, task_status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);

CREATE TRIGGER trg_teams_set_updated_at
BEFORE UPDATE ON teams
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_roles_set_updated_at
BEFORE UPDATE ON roles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_members_set_updated_at
BEFORE UPDATE ON members
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tasks_set_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
```

---

## 8. 示例种子数据建议

为了支持前端静态/半静态联调，可准备如下示例数据：

- `teams`
  - `ai-team`
- `roles`
  - `pm`
  - `frontend`
  - `backend`
  - `designer`
  - `ai-agent`
- `members`
  - Alice / PM
  - Bob / Frontend
  - Carol / Backend
  - Diana / Designer
  - Agent-01 / AI Agent
- `tasks`
  - Dashboard layout / in_progress
  - Team card summary / done
  - Task status widget / todo
  - Data integration plan / blocked

这将直接支持仪表盘展示：
- 总成员数
- 角色数量
- 任务状态分布
- 成员列表

---

## 9. 典型查询示例

### 9.1 查询团队总览指标

```sql
SELECT
  t.id,
  t.name,
  COUNT(DISTINCT m.id) FILTER (WHERE m.is_deleted = FALSE) AS member_count,
  COUNT(DISTINCT m.role_id) FILTER (WHERE m.is_deleted = FALSE) AS role_count,
  COUNT(DISTINCT tk.id) FILTER (WHERE tk.is_deleted = FALSE) AS task_count
FROM teams t
LEFT JOIN members m ON m.team_id = t.id
LEFT JOIN tasks tk ON tk.team_id = t.id
WHERE t.code = 'ai-team'
  AND t.is_deleted = FALSE
GROUP BY t.id, t.name;
```

### 9.2 查询成员列表

```sql
SELECT
  m.id,
  m.name,
  r.name AS role_name,
  m.member_status,
  m.avatar_url
FROM members m
JOIN roles r ON r.id = m.role_id
WHERE m.team_id = $1
  AND m.is_deleted = FALSE
ORDER BY m.name;
```

### 9.3 查询任务状态摘要

```sql
SELECT
  task_status,
  COUNT(*) AS total
FROM tasks
WHERE team_id = $1
  AND is_deleted = FALSE
GROUP BY task_status
ORDER BY task_status;
```

---

## 10. 后续演进建议

若产品从静态 HTML 演进为真实数据驱动版本，建议按以下顺序扩展：

1. **成员多角色支持**
   - 新增 `member_roles(member_id, role_id)`
2. **成员多团队支持**
   - 重构为 `members` + `team_members`
3. **项目维度**
   - 新增 `projects`，让任务归属项目
4. **任务历史/审计**
   - 新增 `task_status_histories`
5. **仪表盘指标缓存**
   - 新增聚合表或物化视图，优化大数据量下的 dashboard 查询

---

## 11. 结论
当前推荐采用 4 张核心表：
- `teams`
- `roles`
- `members`
- `tasks`

该方案优点：
- 与当前 MVP 页面需求直接对应
- 结构简单，便于快速落地
- 满足成员、角色、任务状态三类仪表盘核心信息
- 保留标准审计字段、软删除、显式外键、索引与 migration 基础设施

对当前项目而言，这是一个**足够小但可扩展**的数据库起点。
