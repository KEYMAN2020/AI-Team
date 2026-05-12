"""
knowledge_base.py — 项目知识库
================================
超越 hot_context（近3条任务）的长期记忆。
记录架构决策、编码规范、踩过的坑、领域词汇表。

目录：knowledge/
  decisions.md   架构决策记录（ADR）
  standards.md   编码规范
  gotchas.md     已知坑和解决方案
  glossary.md    领域词汇表
  postmortems.md 故障复盘

任何角色都可以读取知识库，PM/ARCH/DBG/CR 有权写入。
"""

import re
from datetime import datetime
from pathlib import Path

KB_DIR = Path("knowledge")

SECTIONS = {
    "decisions":   "decisions.md",
    "standards":   "standards.md",
    "gotchas":     "gotchas.md",
    "glossary":    "glossary.md",
    "postmortems": "postmortems.md",
}

# 每个角色默认读取哪些知识库章节
ROLE_KB_SECTIONS = {
    "pm":       ["decisions", "gotchas"],
    "product":  ["decisions", "glossary"],
    "architect":["decisions", "standards", "gotchas"],
    "ux":       ["standards", "glossary"],
    "frontend": ["standards", "gotchas"],
    "backend":  ["standards", "gotchas", "decisions"],
    "dba":      ["decisions", "gotchas"],
    "devops":   ["decisions", "gotchas"],
    "debug":    ["gotchas", "postmortems"],
    "reviewer": ["standards"],
    "tester":   ["standards", "gotchas"],
}


# ── 初始化 ────────────────────────────────────────

def init_knowledge_base(project_name: str = "") -> None:
    """初始化知识库，创建各章节文件。"""
    KB_DIR.mkdir(exist_ok=True)
    header = f"# 项目知识库\n项目：{project_name or '未命名'}\n初始化：{datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n"

    defaults = {
        "decisions.md":   header + "# 架构决策记录（ADR）\n\n（暂无记录）\n",
        "standards.md":   header + _default_standards(),
        "gotchas.md":     header + _default_gotchas(),
        "glossary.md":    header + "# 领域词汇表\n\n（暂无记录）\n",
        "postmortems.md": header + "# 故障复盘\n\n（暂无记录）\n",
    }
    for filename, content in defaults.items():
        path = KB_DIR / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    print(f"✅ 知识库已初始化：{KB_DIR}/")


# ── 读取 ─────────────────────────────────────────

def read_section(section: str) -> str:
    """读取指定章节内容。"""
    filename = SECTIONS.get(section)
    if not filename:
        return f"[错误] 未知章节：{section}"
    path = KB_DIR / filename
    if not path.exists():
        return f"[{section}] 章节不存在，请先运行 init_knowledge_base()"
    return path.read_text(encoding="utf-8")


def build_kb_context(role: str) -> str:
    """
    为指定角色构建知识库上下文注入内容。
    只注入该角色需要的章节，控制 token 数量。
    """
    sections = ROLE_KB_SECTIONS.get(role, [])
    if not sections:
        return ""

    parts = []
    for sec in sections:
        content = read_section(sec)
        # 截取关键内容，避免注入过多
        lines = content.split("\n")
        # 跳过文件头部（标题和初始化信息）
        body_lines = [l for l in lines if l.strip() and not l.startswith("#")]
        if body_lines and body_lines[0] != "（暂无记录）":
            preview = "\n".join(body_lines[:20])
            if len(body_lines) > 20:
                preview += f"\n... [共 {len(body_lines)} 行，完整内容见 knowledge/{SECTIONS[sec]}]"
            parts.append(f"[知识库：{sec}]\n{preview}")

    if not parts:
        return ""
    return "\n\n".join(parts)


# ── 写入 ─────────────────────────────────────────

def add_adr(title: str, context: str, decision: str,
            consequences: str, status: str = "已采纳") -> None:
    """
    添加架构决策记录（Architecture Decision Record）。
    ARCH 或 PM 在做重要技术决策时调用。
    """
    path = KB_DIR / "decisions.md"
    _ensure_exists(path)

    # 统计已有 ADR 数量
    content = path.read_text(encoding="utf-8")
    adr_count = content.count("## ADR-") + 1

    entry = f"""
## ADR-{adr_count:03d}：{title}

**状态**：{status}
**日期**：{datetime.now().strftime('%Y-%m-%d')}

**背景**：{context}

**决策**：{decision}

**影响**：{consequences}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"✅ ADR-{adr_count:03d} 已记录：{title}")


def add_gotcha(title: str, symptom: str, cause: str,
               solution: str, affected_roles: list = None) -> None:
    """
    记录已踩的坑，供其他角色和未来项目参考。
    DBG 修完 Bug 后应调用此函数。
    """
    path = KB_DIR / "gotchas.md"
    _ensure_exists(path)

    roles_str = "、".join(affected_roles) if affected_roles else "通用"
    entry = f"""
## {title}

**影响角色**：{roles_str}
**日期**：{datetime.now().strftime('%Y-%m-%d')}

**症状**：{symptom}

**根因**：{cause}

**解决方案**：{solution}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"✅ 坑已记录：{title}")


def add_postmortem(incident: str, timeline: str, root_cause: str,
                   impact: str, action_items: list) -> None:
    """记录故障复盘。"""
    path = KB_DIR / "postmortems.md"
    _ensure_exists(path)

    items_str = "\n".join(f"  - [ ] {item}" for item in action_items)
    entry = f"""
## {incident}

**日期**：{datetime.now().strftime('%Y-%m-%d')}
**影响**：{impact}

**时间线**：{timeline}

**根因**：{root_cause}

**行动项**：
{items_str}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"✅ 故障复盘已记录：{incident}")


def update_standards(section: str, content: str) -> None:
    """更新编码规范（追加到对应章节）。"""
    path = KB_DIR / "standards.md"
    _ensure_exists(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n### {section}\n{content}\n")
    print(f"✅ 规范已更新：{section}")


def add_glossary(term: str, definition: str, example: str = "") -> None:
    """添加领域词汇。"""
    path = KB_DIR / "glossary.md"
    _ensure_exists(path)
    entry = f"\n**{term}**：{definition}"
    if example:
        entry += f"（例：{example}）"
    entry += "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


# ── 默认编码规范 ──────────────────────────────────

def _default_standards() -> str:
    return """# 编码规范

> 所有成员遵守本规范。CR（代码审查员）在 Review 时以此为基准。

## 通用规范

- **命名**：变量/函数用 camelCase（JS/TS）或 snake_case（Python），类用 PascalCase
- **函数长度**：单个函数不超过 50 行，超过则拆分
- **注释**：公共函数必须有 docstring/JSDoc，复杂逻辑必须有行内注释
- **魔法数字**：禁止，提取为具名常量
- **错误处理**：不允许空 catch，至少记录日志
- **提交信息**：`[类型] 简短描述`，类型为 feat/fix/refactor/test/docs/chore

## 前端规范（FE）

- 组件文件：PascalCase，每文件一个组件
- Props 必须有类型声明（TypeScript 或 PropTypes）
- 禁止在组件内直接调用 API，统一通过 service 层
- CSS：使用项目约定的 CSS-in-JS 或 CSS Module，禁止内联样式（除动态值）
- 所有用户输入必须做 XSS 防护
- 每个组件必须有对应的单元测试文件（*.test.tsx）

## 后端规范（BE）

- API 响应格式统一：`{"data": ..., "code": 0, "msg": "ok"}`
- 错误码定义在 `constants/errors.py` 中，禁止硬编码
- 数据库操作必须通过 ORM，禁止拼接 SQL 字符串
- 敏感字段（密码、token）禁止出现在日志中
- 所有外部输入必须经过 Pydantic/Zod 等校验
- 每个 service 方法必须有单元测试，覆盖正向+异常路径

## 数据库规范（DBA/BE）

- 表名：复数 snake_case（users, order_items）
- 必填字段：id、created_at、updated_at
- 外键字段命名：`{table_name}_id`
- 索引命名：`idx_{table}_{field}`
- Migration 必须包含回滚脚本

## 测试规范（QA/FE/BE）

- 单元测试覆盖率目标：核心逻辑 ≥ 80%
- 测试命名：`test_[被测函数]_[场景]_[预期结果]`
- 禁止在测试中连接真实数据库，使用 mock 或测试数据库
- 每个 Bug 修复必须附带回归测试用例
"""


def _default_gotchas() -> str:
    """AI 开发团队的常见坑（种子数据），避免重复踩坑。"""
    return """# 已知坑与解决方案

> DEBUG / TESTER 修完 Bug 后请在这里记录，让整个团队受益。

## 大模型输出格式不稳定
**影响角色**：通用
**日期**：2026-05-12

**症状**：LLM 输出中 <dag> JSON 格式错误、state_update 解析失败、偶尔不按模板输出

**根因**：非推理模型（temperature=0）输出仍有随机性；推理模型在长上下文下会「遗忘」格式要求

**解决方案**：
1. 关键标签（<dag>、<state_update>）用独立代码块包裹
2. runner 层的 _extract_dag / parse_state_update 永远有 fallback 逻辑
3. 对 JSON 字段做 json.JSONDecodeError 容错

---

## Sub_requests 循环爆炸
**影响角色**：PM, UX, ARCHITECT
**日期**：2026-05-12

**症状**：Agent A 发 sub_request 给 Agent B，Agent B 再发 sub_request 给 Agent C，
导致 token 消耗剧增、超时

**根因**：sub_request 嵌套调用，没有深度限制

**解决方案**：
1. MAX_SUB_REQUESTS=3 限制单 Agent 发起的 sub_request 数量
2. sub_request 不递归（_handle_sub_requests 不处理 sub agent 输出中的 sub_requests）
3. 如果信息不足，Agent 应在输出中标注「缺少 XXX，建议下游补充」

---

## 工具调用死循环
**影响角色**：FRONTEND, BACKEND, DEVOPS
**日期**：2026-05-12

**症状**：Agent 在 tool_loop 中反复读取同一文件、循环调用 web_search 相同关键词

**根因**：模型在 tool_use → tool_result 循环中无法收敛，反复要求同一操作

**解决方案**：
1. max_iter=5 硬上限
2. 如果达到上限，最后请求一次不传 tools（让模型输出纯文本）
3. 工具返回结果包含有用信息后，模型应继续文本输出而非重复调用
"""


def _ensure_exists(path: Path) -> None:
    if not path.exists():
        KB_DIR.mkdir(exist_ok=True)
        path.write_text(f"# {path.stem}\n\n", encoding="utf-8")
