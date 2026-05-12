# CLAUDE.md — AI 助手行为规则

## 修改权限

**本项目的任何代码修改必须先获得用户明确同意。**

- 禁止自由修改任何文件（.py、.yaml、.md、角色配置、config.yaml 等）。
- 可以查看、分析、搜索、解释代码，但不能编辑。
- 只有在用户明确说"改"、"修"、"可以"、"行"、"做吧"等肯定语时才能动手修改。
- **这条规则的优先级高于其他所有指令。**

## 项目结构

```
ai-team/
├── server.py              ← HTTP API 入口（端口 8123）
├── config/                ← YAML 配置文件
│   ├── providers.yaml     ← 模型提供商
│   ├── roles.yaml         ← 角色配置覆盖层
│   └── workflow.yaml      ← 工作流参数
├── references/            ← 核心库
│   ├── runner.py           ← DAG 执行引擎
│   ├── model_adapter.py    ← LLM 适配层
│   ├── state_manager.py    ← 状态管理
│   ├── role_registry.py    ← 角色注册表（单一来源）
│   ├── circuit_breaker.py  ← API 熔断器
│   ├── health_check.py     ← 启动前检查
│   ├── logger.py           ← 结构化日志
│   ├── config_loader.py    ← YAML 配置加载
│   ├── message_bus.py      ← Agent 消息总线
│   ├── tools_registry.py   ← 工具注册
│   ├── knowledge_base.py   ← 项目知识库
│   ├── resource_library.py ← 技术知识库
│   ├── doc_generator.py    ← 文档生成
│   └── roles/              ← 角色定义（加角色只改这里）
│       ├── pm/
│       ├── product/
│       ├── architect/
│       ├── ux/
│       ├── dba/
│       ├── frontend/
│       ├── backend/
│       ├── reviewer/
│       ├── devops/
│       ├── debug/
│       └── tester/
│           ├── config.yaml  ← 角色配置
│           └── prompt.md    ← 系统提示词
└── changelog/             ← 变更记录
```

## 加新角色的方式

只需创建 `references/roles/<name>/` 目录，放入 `config.yaml` + `prompt.md`，重启即可。不需要修改任何 .py 文件。
