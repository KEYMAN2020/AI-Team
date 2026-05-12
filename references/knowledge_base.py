"""
knowledge_base.py — 项目知识库 v2.0
====================================
分两层隔离 Agent 幻觉风险：

  curated/  ← 人类编写，始终注入上下文（100% 信任）
  auto/     ← Agent 自动生成，注入时带警告标记（可能幻觉）

目录：
  knowledge/
  ├── curated/
  │   ├── standards.md   编码规范
  │   ├── glossary.md    领域词汇表
  │   └── gotchas.md     种子踩坑经验（人类编写）
  └── auto/
      ├── gotchas.md     Agent 自动归档的坑
      ├── decisions.md   Agent 生成的架构决策
      ├── postmortems.md Agent 生成的故障复盘
      └── _manifest.json 条目索引（谁、何时、是否已审查）
"""

import json
import re
from datetime import datetime
from pathlib import Path

KB_DIR = Path("knowledge")
CURATED_DIR = KB_DIR / "curated"
AUTO_DIR    = KB_DIR / "auto"
MANIFEST_PATH = AUTO_DIR / "_manifest.json"

# curated/ 章节（人类编写，绝对信任）
CURATED_SECTIONS = {
    "standards": "standards.md",
    "glossary":  "glossary.md",
    "gotchas":   "gotchas.md",  # 种子数据，不含 Agent 自动写入
}

# auto/ 章节（Agent 生成，可能包含幻觉）
AUTO_SECTIONS = {
    "decisions":   "decisions.md",
    "gotchas":     "gotchas.md",
    "postmortems": "postmortems.md",
}

# 每个角色读取的知识库章节（标注来源类型）
ROLE_KB_SECTIONS = {
    # key = (source_type, section)
    "pm":        [("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "product":   [("auto", "decisions"), ("curated", "glossary")],
    "architect": [("auto", "decisions"), ("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
    "ux":        [("curated", "standards"), ("curated", "glossary")],
    "frontend":  [("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
    "backend":   [("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas"), ("auto", "decisions")],
    "dba":       [("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "devops":    [("auto", "decisions"), ("curated", "gotchas"), ("auto", "gotchas")],
    "debug":     [("curated", "gotchas"), ("auto", "gotchas"), ("auto", "postmortems")],
    "reviewer":  [("curated", "standards")],
    "tester":    [("curated", "standards"), ("curated", "gotchas"), ("auto", "gotchas")],
}

# ── 初始化 ────────────────────────────────────────

def init_knowledge_base(project_name: str = "") -> None:
    """初始化知识库，创建 curated/ 和 auto/ 目录结构。"""
    CURATED_DIR.mkdir(parents=True, exist_ok=True)
    AUTO_DIR.mkdir(parents=True, exist_ok=True)

    # —— curated/ ——
    curated_defaults = {
        "standards.md": _default_standards(),
        "gotchas.md":   _default_gotchas(),
        "glossary.md":  "# 领域词汇表\n\n（暂无记录）\n",
    }
    for filename, content in curated_defaults.items():
        path = CURATED_DIR / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    # —— auto/ ——
    for filename in AUTO_SECTIONS.values():
        path = AUTO_DIR / filename
        if not path.exists():
            path.write_text(f"# {path.stem}\n\n（暂无自动生成条目）\n", encoding="utf-8")

    # —— manifest ——
    if not MANIFEST_PATH.exists():
        MANIFEST_PATH.write_text(json.dumps({
            "project": project_name or "未命名",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "entries": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 知识库已初始化：{KB_DIR}/ (curated + auto)")


# ── 读取 ─────────────────────────────────────────

def read_section(section: str, source: str = "curated") -> str:
    """读取指定来源的章节内容。source = 'curated' | 'auto'"""
    sections_map = CURATED_SECTIONS if source == "curated" else AUTO_SECTIONS
    base_dir = CURATED_DIR if source == "curated" else AUTO_DIR
    filename = sections_map.get(section)
    if not filename:
        return f"[错误] 未知章节：{section}"
    path = base_dir / filename
    if not path.exists():
        return f"[{section}] 章节不存在"
    return path.read_text(encoding="utf-8")


def build_kb_context(role: str) -> str:
    """
    为指定角色构建知识库上下文。
    - curated/ 内容不加警告（人类编写）
    - auto/ 内容标注「未经人工审查，仅供参考」
    """
    sections = ROLE_KB_SECTIONS.get(role, [])
    if not sections:
        return ""

    parts = []
    for source, sec in sections:
        content = read_section(sec, source)
        lines = content.split("\n")
        # 过滤空行和文件级标题（# ），保留条目级标题（##）和内容
        body_lines = [l for l in lines if l.strip() and not re.match(r'^# [^#]', l)]
        if not body_lines or body_lines[0].startswith("（暂无"):
            continue

        preview = "\n".join(body_lines[:15])
        if len(body_lines) > 15:
            preview += f"\n... [共 {len(body_lines)} 行，完整内容见 knowledge/{source}/{sec}.md]"

        if source == "curated":
            parts.append(f"[知识库：{sec}]\n{preview}")
        else:
            parts.append(f"[自动存档：{sec} —— [!] 以下为 Agent 自动生成，未经人工审查，可能有误，仅供参考]\n{preview}")

    return "\n\n".join(parts) if parts else ""


# ── 写入（curated/ — 人类维护）────────────────────

def update_standards(section: str, content: str) -> None:
    """更新编码规范。人类操作，写入 curated/。"""
    path = CURATED_DIR / "standards.md"
    _ensure_exists(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n### {section}\n{content}\n")
    print(f"[OK] 规范已更新（curated）：{section}")


def add_glossary(term: str, definition: str, example: str = "") -> None:
    """添加领域词汇。人类操作，写入 curated/。"""
    path = CURATED_DIR / "glossary.md"
    _ensure_exists(path)
    entry = f"\n**{term}**：{definition}"
    if example:
        entry += f"（例：{example}）"
    entry += "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


# ── 写入（auto/ — Agent 自动生成）─────────────────

def _record_in_manifest(file: str, title: str, added_by: str) -> None:
    """在 manifest 中记录一条自动生成条目（便于审查）。"""
    if not MANIFEST_PATH.exists():
        return
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = {
        "file":      file,
        "title":     title,
        "added_at":  datetime.now().isoformat(timespec="seconds"),
        "added_by":  added_by,
        "reviewed":  False,
    }
    manifest.setdefault("entries", []).append(entry)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def add_adr(title: str, context: str, decision: str,
            consequences: str, status: str = "已采纳") -> None:
    """添加架构决策记录。Agent 调用，写入 auto/。"""
    path = AUTO_DIR / "decisions.md"
    _ensure_exists(path)

    content = path.read_text(encoding="utf-8")
    adr_count = content.count("## ADR-") + 1

    entry = f"""
## ADR-{adr_count:03d}：{title}

**状态**：{status}
**日期**：{datetime.now().strftime('%Y-%m-%d')}
**来源**：Agent 生成，待审查

**背景**：{context}

**决策**：{decision}

**影响**：{consequences}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/decisions.md", f"ADR-{adr_count:03d}：{title}", "agent")
    print(f"[OK] ADR-{adr_count:03d} 已记录（auto）：{title}")


def add_gotcha(title: str, symptom: str, cause: str,
               solution: str, affected_roles: list = None) -> None:
    """
    记录踩坑经验。Agent 调用（如 QA→DBG 循环），写入 auto/。
    如需加入 curated/，人类审查后调用 promote_to_curated()。
    """
    path = AUTO_DIR / "gotchas.md"
    _ensure_exists(path)

    roles_str = "、".join(affected_roles) if affected_roles else "通用"
    entry = f"""
## {title}

**影响角色**：{roles_str}
**日期**：{datetime.now().strftime('%Y-%m-%d')}
**来源**：Agent 自动生成，待审查

**症状**：{symptom}

**根因**：{cause}

**解决方案**：{solution}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/gotchas.md", title, "agent")
    print(f"[OK] 坑已记录（auto）：{title}")


def add_postmortem(incident: str, timeline: str, root_cause: str,
                   impact: str, action_items: list) -> None:
    """记录故障复盘。Agent 调用，写入 auto/。"""
    path = AUTO_DIR / "postmortems.md"
    _ensure_exists(path)

    items_str = "\n".join(f"  - [ ] {item}" for item in action_items)
    entry = f"""
## {incident}

**日期**：{datetime.now().strftime('%Y-%m-%d')}
**影响**：{impact}
**来源**：Agent 生成，待审查

**时间线**：{timeline}

**根因**：{root_cause}

**行动项**：
{items_str}

---
"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    _record_in_manifest("auto/postmortems.md", incident, "agent")
    print(f"[OK] 故障复盘已记录（auto）：{incident}")


# ── 审查与提升 ───────────────────────────────────

def list_pending_review() -> list[dict]:
    """列出所有待人工审查的 auto/ 条目。"""
    if not MANIFEST_PATH.exists():
        return []
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [e for e in manifest.get("entries", []) if not e.get("reviewed")]


def promote_to_curated(file: str, entry_title: str) -> bool:
    """
    人工审查后，将 auto/ 中的条目提升到 curated/。
    从 auto 文件删除该条目，追加到对应的 curated 文件。
    """
    # 确定 auto 和 curated 路径
    auto_path = AUTO_DIR / (file.split("/")[-1] if "/" in file else file)
    section_name = auto_path.stem  # e.g. "gotchas"
    curated_path = CURATED_DIR / f"{section_name}.md"

    if not auto_path.exists():
        print(f"[ERROR] auto 文件不存在：{auto_path}")
        return False

    # 从 auto 文件中提取该条目
    content = auto_path.read_text(encoding="utf-8")
    pattern = rf"## {re.escape(entry_title)}.*?(?=## |\Z)"
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        print(f"[ERROR] 未找到条目：{entry_title}")
        return False

    # 追加到 curated（去掉「Agent 生成」标记）
    entry = m.group(0).replace("**来源**：Agent 生成，待审查\n", "")
    _ensure_exists(curated_path)
    with open(curated_path, "a", encoding="utf-8") as f:
        f.write(entry)

    # 从 auto 文件中移除
    new_content = content[:m.start()] + content[m.end():]
    auto_path.write_text(new_content, encoding="utf-8")

    # 更新 manifest
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for e in manifest.get("entries", []):
            if e.get("title") == entry_title and file in e.get("file", ""):
                e["reviewed"] = True
                e["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                break
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 已提升到 curated：{entry_title}")
    return True


# ── 默认内容（人类编写）──────────────────────────

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
    """人类编写的种子坑，Agent 不会自动改这里。"""
    return """# 已知坑与解决方案

> 以下为人类整理的种子经验。Agent 自动归档的坑在 auto/gotchas.md。

## 大模型输出格式不稳定

**影响角色**：通用
**日期**：2026-05-12
**来源**：人工总结

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
**来源**：人工总结

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
**来源**：人工总结

**症状**：Agent 在 tool_loop 中反复读取同一文件、循环调用 web_search 相同关键词

**根因**：模型在 tool_use → tool_result 循环中无法收敛，反复要求同一操作

**解决方案**：
1. max_iter=5 硬上限
2. 如果达到上限，最后请求一次不传 tools（让模型输出纯文本）
3. 工具返回结果包含有用信息后，模型应继续文本输出而非重复调用
"""


# ── 辅助 ─────────────────────────────────────────

def _ensure_exists(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n\n", encoding="utf-8")
