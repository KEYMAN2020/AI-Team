# ai-team Dashboard 系统架构与接口约定

## 1. 背景与架构目标
基于已确认的需求，当前项目最适合先按 **MVP 静态 HTML 仪表盘** 推进，但为了支持后续从静态演示平滑演进到动态数据驱动版本，建议从一开始采用“**静态前端优先、API 可演进预留**”的架构思路。

本设计结论：
- **MVP 第一阶段**：交付单页静态 HTML dashboard，可离线打开演示。
- **扩展第二阶段**：通过轻量 API 提供团队、成员、任务、指标数据，让静态页可逐步升级为动态仪表盘。
- **系统复杂度控制**：当前不引入登录、编辑、数据库写操作等复杂能力，仅设计只读查询接口。

---

## 2. 总体架构

### 2.1 分层架构

```text
+--------------------------------------------------+
|                  Browser / User                  |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|         Frontend: Static HTML Dashboard          |
|  - index.html                                    |
|  - styles.css                                    |
|  - app.js (可选，后续动态化时启用)               |
+--------------------------------------------------+
                         |
                         | HTTP/JSON（第二阶段）
                         v
+--------------------------------------------------+
|            Backend API Layer (Read Only)         |
|  - Dashboard summary API                         |
|  - Members API                                   |
|  - Tasks/Status API                              |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|              Data Access / Service Layer         |
|  - Dashboard service                             |
|  - Member service                                |
|  - Task service                                  |
+--------------------------------------------------+
                         |
                         v
+--------------------------------------------------+
|          Data Source Layer / Mock or DB          |
|  Phase 1: local mock JSON / hardcoded data       |
|  Phase 2: relational database                    |
+--------------------------------------------------+
```

### 2.2 架构说明
- **前端层**：MVP 时以静态 HTML 为核心，保证可快速预览和低集成成本。
- **API 层**：虽然当前需求不要求必须实现后端，但应先定义接口契约，避免后续前后端反复调整。
- **服务层**：统一聚合团队概览、成员分布、任务状态等数据。
- **数据层**：第一阶段可直接使用 mock 数据；后续可迁移到关系型数据库。

---

## 3. MVP 推荐模块划分

### 3.1 前端页面模块
单页 dashboard 建议拆为以下区域：
1. **Header 顶部区**
   - 团队名称
   - 页面标题
   - 最后更新时间
2. **Overview 概览卡片区**
   - 总成员数
   - 角色数量
   - 进行中任务数
   - 已完成任务数
3. **Members 成员列表区**
   - 成员名称
   - 角色
   - 当前状态
4. **Role Distribution 角色分布区**
   - 各角色人数统计
5. **Task Summary 任务状态摘要区**
   - todo / in_progress / done / blocked 等分类统计
6. **Risks / Notes 区域（可选）**
   - 当前风险
   - 备注说明

### 3.2 后端领域模块
若进入动态化开发，建议按以下模块组织：
- `dashboard`：聚合首页概览数据
- `members`：成员列表与角色统计
- `tasks`：任务状态汇总
- `meta`：页面基础元信息（团队名、更新时间）

---

## 4. 技术选型建议

### 4.1 第一阶段（当前最优）
- **前端**：HTML + CSS + Vanilla JavaScript
- **数据来源**：静态 JSON 或 JS 常量
- **部署方式**：本地文件打开 / 静态托管

适用原因：
- 满足“纯 HTML 可预览”要求
- 实现成本最低
- 便于快速演示和需求确认

### 4.2 第二阶段（需要动态数据时）
- **前端**：保留原静态结构，可逐步增加 JS 渲染
- **后端**：Node.js/Express、Python/FastAPI、或任一轻量 REST 服务
- **数据库**：PostgreSQL 优先

适用原因：
- 仪表盘主要是只读聚合查询，REST API 足够
- PostgreSQL 适合后续成员、任务、审计字段扩展

---

## 5. 数据模型建议
以下为接口层推荐的数据对象，不要求此阶段立即建表，但建议后续保持一致。

### 5.1 Team
```json
{
  "id": "team_001",
  "name": "AI Team",
  "description": "AI collaboration dashboard demo",
  "last_updated_at": "2026-05-24T10:00:00Z"
}
```

### 5.2 Member
```json
{
  "id": "member_001",
  "name": "Alice",
  "role": "Product Manager",
  "status": "active",
  "avatar_url": null
}
```

### 5.3 Task Summary Item
```json
{
  "status": "in_progress",
  "count": 6
}
```

### 5.4 Dashboard Summary
```json
{
  "team_name": "AI Team",
  "total_members": 8,
  "total_roles": 5,
  "tasks_todo": 3,
  "tasks_in_progress": 6,
  "tasks_done": 12,
  "tasks_blocked": 1,
  "last_updated_at": "2026-05-24T10:00:00Z"
}
```

---

## 6. 接口设计原则

### 6.1 总体原则
- 当前阶段接口以 **只读查询** 为主
- 响应格式统一为 JSON
- 字段命名使用 `snake_case`
- 时间统一使用 ISO 8601 UTC 字符串
- 列表接口默认不分页（MVP 数据量小），后续如成员变多再加分页
- 错误码遵循项目知识库建议：
  - `1xxxx` 业务错误
  - `2xxxx` 权限错误
  - `3xxxx` 参数错误
  - `5xxxx` 系统错误

### 6.2 统一响应格式

#### 成功响应
```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

#### 错误响应
```json
{
  "code": 30001,
  "message": "invalid parameter",
  "data": null
}
```

---

## 7. 接口约定

### 7.1 获取仪表盘首页概览
**GET** `/api/dashboard/summary`

**用途**：返回顶部概览卡片与基础统计信息。

**请求参数**：无

**响应示例**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "team_name": "AI Team",
    "total_members": 8,
    "total_roles": 5,
    "tasks_todo": 3,
    "tasks_in_progress": 6,
    "tasks_done": 12,
    "tasks_blocked": 1,
    "last_updated_at": "2026-05-24T10:00:00Z"
  }
}
```

---

### 7.2 获取成员列表
**GET** `/api/members`

**用途**：返回成员列表，用于成员卡片或表格展示。

**请求参数**：
| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| role | query | string | 否 | 按角色过滤 |
| status | query | string | 否 | 按成员状态过滤，如 active / offline |

**响应示例**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "member_001",
        "name": "Alice",
        "role": "Product Manager",
        "status": "active",
        "avatar_url": null
      },
      {
        "id": "member_002",
        "name": "Bob",
        "role": "Frontend Engineer",
        "status": "active",
        "avatar_url": null
      }
    ]
  }
}
```

---

### 7.3 获取角色分布统计
**GET** `/api/members/role-distribution`

**用途**：返回角色聚合统计，用于图表或统计卡片。

**请求参数**：无

**响应示例**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "role": "Product Manager",
        "count": 1
      },
      {
        "role": "Frontend Engineer",
        "count": 2
      },
      {
        "role": "Backend Engineer",
        "count": 2
      }
    ]
  }
}
```

---

### 7.4 获取任务状态摘要
**GET** `/api/tasks/summary`

**用途**：返回任务状态统计，用于状态摘要区。

**请求参数**：无

**响应示例**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "status": "todo",
        "count": 3
      },
      {
        "status": "in_progress",
        "count": 6
      },
      {
        "status": "done",
        "count": 12
      },
      {
        "status": "blocked",
        "count": 1
      }
    ]
  }
}
```

---

### 7.5 获取页面元信息（可选）
**GET** `/api/meta`

**用途**：返回团队名称、环境说明、更新时间等页面公共元信息。

**请求参数**：无

**响应示例**：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "team_id": "team_001",
    "team_name": "AI Team",
    "description": "AI collaboration dashboard demo",
    "last_updated_at": "2026-05-24T10:00:00Z"
  }
}
```

---

## 8. 静态 HTML 阶段与动态 API 阶段的衔接方式

### 8.1 第一阶段：纯静态
- 数据直接写在 HTML 或本地 JS 常量中
- 不依赖后端
- 适合快速评审视觉结构和信息架构

### 8.2 第二阶段：半动态
- 保留 HTML 布局
- 使用 `app.js` 调用上述 GET 接口
- 将概览卡片、成员列表、任务摘要改为动态渲染

### 8.3 第三阶段：生产化
- 接入真实数据库
- 增加缓存与监控
- 视需求增加权限控制、筛选、搜索、分页

---

## 9. 非功能性约定

### 9.1 性能
- MVP 页面应在普通桌面浏览器中快速打开
- 单个接口响应目标建议 < 500ms（动态阶段）

### 9.2 安全
- 当前 MVP 可不启用鉴权，但若后续接入真实团队数据，应增加访问控制
- 前端展示时需对动态文本做 XSS 防护

### 9.3 可维护性
- 前端页面模块化拆分命名
- API 字段保持稳定，避免频繁重命名
- mock 数据结构应与未来 API 返回结构尽量一致

---

## 10. 风险与待确认项
1. **ai-team 的业务定义未完全明确**：是展示真实组织团队，还是 AI Agent 协作团队，会影响字段设计。
2. **任务模型未定义**：目前仅适合做状态汇总，不建议先设计复杂任务详情接口。
3. **是否需要响应式与图表交互**：会影响前端结构和 JS 依赖。
4. **是否需要鉴权**：若仅演示可省略；若上线内部使用则需补充。

---

## 11. 推荐结论
建议后续团队按以下顺序推进：
1. **UX/FE** 基于本架构先完成单页静态 HTML 仪表盘原型
2. 使用 **mock 数据结构严格对齐本接口定义**
3. 如业务确认需要动态数据，再由 BE 按本接口实现只读 API
4. 最后根据真实数据情况补充数据库 schema 与分页/筛选能力

该方案兼顾了：
- 当前需求信息不足时的快速落地
- 后续演进到动态 dashboard 的可扩展性
- 最小化返工风险
