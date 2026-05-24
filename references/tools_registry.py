"""
tools_registry.py — 角色工具注册表
====================================
每个角色绑定它职责范围内需要的工具。
角色自己决定何时调用工具，框架负责执行并把结果回传。

工具定义格式兼容：
  - Anthropic tool_use
  - OpenAI / DeepSeek function calling
  - Gemini function declarations

工具执行：
  model_adapter.py 检测到 tool_use 后调用 execute_tool()，
  把结果作为 tool_result 回传给模型，直到模型给出最终文本输出。
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Optional

# ════════════════════════════════════════════════════
# 工具定义（统一格式，model_adapter 按需转换）
# ════════════════════════════════════════════════════

TOOL_DEFS = {

    "web_search": {
        "name": "web_search",
        "description": "搜索互联网获取最新信息。适合查阅库文档、技术规范、最佳实践、错误解决方案。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，尽量简洁精确"}
            },
            "required": ["query"]
        }
    },

    "code_run": {
        "name": "code_run",
        "description": "在沙盒中执行代码并返回输出。支持 Python、Node.js、bash。用于验证实现逻辑、运行测试、重现 Bug。",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["python", "node", "bash"],
                             "description": "代码语言"},
                "code":     {"type": "string", "description": "要执行的完整代码"},
                "timeout":  {"type": "integer", "description": "超时秒数，默认 30", "default": 30}
            },
            "required": ["language", "code"]
        }
    },

    "file_read": {
        "name": "file_read",
        "description": "读取项目文件内容。用于查看已有代码、配置、上游输出文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "path":       {"type": "string", "description": "文件路径（相对于项目根目录）"},
                "start_line": {"type": "integer", "description": "从第几行开始读（可选）"},
                "end_line":   {"type": "integer", "description": "读到第几行（可选）"}
            },
            "required": ["path"]
        }
    },

    "file_write": {
        "name": "file_write",
        "description": "将内容写入文件。用于保存代码、配置、文档到 outputs/ 目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "文件路径，建议写到 outputs/ 目录"},
                "content": {"type": "string", "description": "文件内容"},
                "mode":    {"type": "string", "enum": ["write", "append"],
                            "description": "写入模式：write=覆盖，append=追加，默认 write"}
            },
            "required": ["path", "content"]
        }
    },

    "bash": {
        "name": "bash",
        "description": "执行 shell 命令。用于部署操作、检查服务状态、查看日志、运行构建命令。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
                "timeout": {"type": "integer", "description": "超时秒数，默认 60"}
            },
            "required": ["command"]
        }
    },

    "resource_search": {
        "name": "resource_search",
        "description": "搜索技术知识储备库，获取最佳实践、设计模式、安全规范等参考。遇到技术决策拿不准时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query":    {"type": "string", "description": "搜索关键词，如 'JWT 认证'、'索引优化'、'React 状态管理'"},
                "category": {"type": "string", "description": "限定搜索范围：frontend/backend/database/security/testing/architecture/devops"}
            },
            "required": ["query"]
        }
    },

    "api_doc_update": {
        "name": "api_doc_update",
        "description": "将接口定义写入 OpenAPI 规范。ARCH 设计完接口后调用，BE 实现后补充细节。",
        "parameters": {
            "type": "object",
            "properties": {
                "method":       {"type": "string", "enum": ["GET","POST","PUT","PATCH","DELETE"]},
                "path":         {"type": "string", "description": "接口路径，如 /api/v1/users/login"},
                "summary":      {"type": "string", "description": "接口简述"},
                "tag":          {"type": "string", "description": "所属功能模块，如 用户认证"},
                "parameters":   {"type": "array", "description": "路径/查询参数列表"},
                "request_body": {"type": "object", "description": "请求体示例（JSON对象）"},
                "responses":    {"type": "object", "description": "响应示例，key为HTTP状态码"},
                "requires_auth":{"type": "boolean", "description": "是否需要JWT鉴权，默认true"}
            },
            "required": ["method", "path", "summary", "tag"]
        }
    },

    "diff_view": {
        "name": "diff_view",
        "description": "对比两段代码或两个文件的差异。用于 Debug 时定位改动，或 QA 对比预期与实际输出。",
        "parameters": {
            "type": "object",
            "properties": {
                "content_a": {"type": "string", "description": "对比基准内容（或文件路径）"},
                "content_b": {"type": "string", "description": "对比目标内容（或文件路径）"},
                "is_file":   {"type": "boolean", "description": "content_a/b 是否为文件路径"}
            },
            "required": ["content_a", "content_b"]
        }
    },

    "ui_ux_search": {
        "name": "ui_ux_search",
        "description": "查询 UI/UX Pro Max 设计知识库。提供专业 UI 风格、配色方案、字体搭配、UX 准则、图表类型和产品类型推荐。适合 UX/设计角色在做设计决策时参考最佳实践。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，如 'dark mode dashboard'、'SaaS landing page'、'glassmorphism'"},
                "domain": {"type": "string", "enum": ["style", "prompt", "color", "chart", "landing", "product", "ux", "typography", "google-fonts"],
                           "description": "搜索领域：style=UI风格, color=配色方案, chart=图表推荐, landing=落地页结构, product=产品类型, ux=UX准则及设计模式, typography=字体搭配"},
                "stack": {"type": "string", "enum": ["react", "nextjs", "vue", "svelte", "astro", "swiftui", "react-native", "flutter", "nuxtjs", "nuxt-ui", "html-tailwind", "shadcn", "jetpack-compose", "angular", "laravel", "threejs"],
                          "description": "技术栈搜索（可选，填此参数后忽略 domain）"},
                "max_results": {"type": "integer", "description": "最大返回条数，默认 3", "default": 3}
            },
            "required": ["query"]
        }
    },
}


# ════════════════════════════════════════════════════
# Tool Categories — 用于 Tool Loadout 动态筛选
# 每个工具标记所属类别和触发关键词
# ════════════════════════════════════════════════════

TOOL_CATEGORIES = {
    "web_search":      {"cats": ["research", "reference"],      "trigger": ["查", "搜", "搜索", "find", "lookup", "查阅", "文档", "规范", "最佳实践", "example"]},
    "code_run":        {"cats": ["dev", "verification"],         "trigger": ["运行", "执行", "测试", "跑", "run", "test", "verify", "验证", "调试", "debug"]},
    "file_read":       {"cats": ["io", "reference"],             "trigger": ["读", "看", "查看", "检查", "read", "check", "open", "查看代码", "查看文件"]},
    "file_write":      {"cats": ["io", "output"],                "trigger": ["写", "创建", "保存", "生成", "write", "create", "save", "generate", "输出"]},
    "bash":            {"cats": ["dev", "ops", "deploy"],        "trigger": ["部署", "启动", "运行", "deploy", "restart", "install", "docker", "容器", "服务", "日志"]},
    "resource_search": {"cats": ["research", "best_practice"],   "trigger": ["知识库", "最佳实践", "设计模式", "规范", "pattern", "best practice", "security"]},
    "api_doc_update":  {"cats": ["documentation", "arch"],       "trigger": ["API", "接口", "endpoint", "OpenAPI", "swagger", "文档化"]},
    "diff_view":       {"cats": ["verification", "debug"],       "trigger": ["对比", "差异", "diff", "区别", "changed", "修改了"]},
    "ui_ux_search":    {"cats": ["design", "research"],          "trigger": ["设计", "风格", "配色", "字体", "UX", "UI", "布局", "landing", "chart", "调色板", "推荐", "美观", "样式"]},
}

def filter_tools_for_task(tools: list[str], task_description: str) -> list[str]:
    """
    根据任务描述关键词动态筛选相关工具（Tool Loadout Management）。
    如果 task_description 为空或没有匹配，返回全部工具。
    过滤逻辑简单高效：检测任务文本中是否包含工具分类的 trigger 关键词。
    """
    if not task_description:
        return tools
    desc_lower = task_description.lower()
    scored = {}
    for t in tools:
        cats = TOOL_CATEGORIES.get(t, {})
        triggers = cats.get("trigger", [])
        # 计算匹配分数：每个匹配关键词 +1
        score = sum(2 for kw in triggers if kw.lower() in desc_lower)
        scored[t] = score
    # 按分数降序排列
    sorted_tools = sorted(tools, key=lambda t: scored.get(t, 0), reverse=True)
    max_score = max(scored.values()) if scored else 0
    if max_score == 0:
        return tools  # 无匹配则返回全部
    threshold = max(1, max_score * 0.3)  # 保留分数 >= 最高分30% 的工具
    filtered = [t for t in sorted_tools if scored.get(t, 0) >= threshold]
    # 无论如何保留 io 类工具（读/写文件是基本操作）
    for t in tools:
        cats = TOOL_CATEGORIES.get(t, {}).get("cats", [])
        if "io" in cats and t not in filtered:
            filtered.append(t)
    return filtered


# ════════════════════════════════════════════════════
# 角色 → 工具绑定
# 每个角色只拿自己需要的工具
# ════════════════════════════════════════════════════

ROLE_TOOLS = {
    # ══ 硬编码 fallback（role_registry 不可用时使用） ══
    "pm":        ["web_search", "resource_search", "file_read", "file_write"],
    "product":   ["web_search", "file_read", "file_write"],
    "architect": ["web_search", "file_read", "file_write", "code_run", "resource_search", "api_doc_update"],
    "ux":        ["web_search", "file_read", "file_write"],
    "dba":       ["code_run", "bash", "file_read", "file_write", "web_search", "resource_search"],
    "frontend":  ["web_search", "resource_search", "code_run", "file_read", "file_write"],
    "backend":   ["web_search", "code_run", "bash", "file_read", "file_write", "resource_search", "api_doc_update"],
    "reviewer":  ["file_read", "diff_view", "web_search", "resource_search", "file_write"],
    "devops":    ["bash", "file_read", "file_write", "web_search", "code_run", "resource_search"],
    "debug":     ["code_run", "bash", "file_read", "file_write", "diff_view", "web_search", "resource_search"],
    "tester":    ["web_search", "resource_search", "code_run", "bash", "file_read", "file_write", "diff_view"],
}

# ── 从 role_registry 覆盖角色工具（优先） ──
try:
    from role_registry import get_role_tools as _get_role_tools, get_all_roles as _get_all_roles
    for _role in _get_all_roles():
        _reg_tools = _get_role_tools(_role)
        if _reg_tools:
            ROLE_TOOLS[_role] = _reg_tools
    del _get_role_tools, _get_all_roles  # 清理模块级变量
except ImportError:
    pass


# ════════════════════════════════════════════════════
# 获取角色工具列表（供 model_adapter 使用）
# ════════════════════════════════════════════════════

def get_tools_for_role(role: str, task_context: str = "") -> list[dict]:
    """返回该角色的工具定义列表（OpenAI/Anthropic 格式）。自动解析别名。
    如果提供了 task_context，会做 Tool Loadout 动态筛选。"""
    try:
        from role_registry import resolve_role as _resolve
        role = _resolve(role) or role
    except ImportError:
        pass
    tool_names = ROLE_TOOLS.get(role, [])
    if task_context:
        tool_names = filter_tools_for_task(tool_names, task_context)
    return [TOOL_DEFS[name] for name in tool_names if name in TOOL_DEFS]

def get_tool_names_for_role(role: str, task_context: str = "") -> list[str]:
    """返回该角色的工具名称列表。自动解析别名。
    如果提供了 task_context，会做 Tool Loadout 动态筛选。"""
    try:
        from role_registry import resolve_role as _resolve
        role = _resolve(role) or role
    except ImportError:
        pass
    tool_names = ROLE_TOOLS.get(role, [])
    if task_context:
        tool_names = filter_tools_for_task(tool_names, task_context)
    return tool_names


# ════════════════════════════════════════════════════
# 工具执行器
# ════════════════════════════════════════════════════

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    执行工具调用，返回结果字符串。
    model_adapter 检测到 tool_use 后调用此函数。
    """
    handlers = {
        "web_search":      _exec_web_search,
        "code_run":        _exec_code_run,
        "file_read":       _exec_file_read,
        "file_write":      _exec_file_write,
        "bash":            _exec_bash,
        "diff_view":       _exec_diff_view,
        "resource_search": _exec_resource_search,
        "api_doc_update":  _exec_api_doc_update,
        "ui_ux_search":    _exec_ui_ux_search,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return f"[错误] 未知工具：{tool_name}"
    try:
        return handler(**tool_input)
    except Exception as e:
        return f"[工具执行错误] {tool_name}: {e}"


def _exec_web_search(query: str) -> str:
    """调用系统 web_search 能力（实际实现替换为你的搜索 API）。"""
    # 接入真实搜索 API 时替换此处
    # 示例：DuckDuckGo、Tavily、Serper 等
    try:
        import urllib.request, urllib.parse
        q = urllib.parse.quote(query)
        # 使用 DuckDuckGo instant answer（无需 API Key）
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        abstract = data.get("AbstractText", "")
        if abstract:
            return f"搜索结果（{query}）：\n{abstract[:1000]}"
        related = data.get("RelatedTopics", [])[:3]
        snippets = [t.get("Text","") for t in related if isinstance(t, dict) and t.get("Text")]
        return f"搜索结果（{query}）：\n" + "\n".join(snippets[:3]) if snippets else f"未找到 '{query}' 的结果"
    except Exception as e:
        return f"搜索失败（{query}）：{e}\n提示：可接入 Tavily/Serper API 获得更好的搜索结果"


# 代码执行危险 pattern 检查（Python）
_CODE_DANGEROUS_PATTERNS = [
    r'\bos\.(system|popen|exec|spawn|remove|unlink|mkdir|chmod|chown)',
    r'\bsubprocess\.', r'\b__import__\s*\(', r'\bimportlib\.import_module',
    r'\beval\s*\(', r'\bexec\s*\(', r'\bcompile\s*\(',
    r'\bopen\s*\([^)]*[\'"]w', r'\bpathlib\.Path\([^)]*\)\.(unlink|rmdir|write_bytes)',
    r'\bshutil\.(rmtree|copy|move)', r'\bsocket\.', r'\brequests\.(post|put|delete|patch)',
    r'\burllib\.', r'\bftp', r'\btelnet',
    r'\bpickle\.(load|loads)', r'\bmarshal\.loads', r'\bctypes\.',
    r'\bsignal\.', r'\bglobals\s*\(\s*\)', r'\bgetattr\s*\(__builtins__',
    r'\bcode\.InteractiveInterpreter',
]


def _check_dangerous_code(code: str) -> Optional[str]:
    """扫描代码中的危险调用，发现则返回警告信息。"""
    import re as _re
    for pattern in _CODE_DANGEROUS_PATTERNS:
        if _re.search(pattern, code):
            return f"[拒绝] 代码包含危险调用：{_re.search(pattern, code).group(0)[:50]}"
    return None


# Bash 危险命令（与 _exec_bash 的 DANGEROUS 集合保持一致）
_BASH_DANGEROUS_CMDS = {
    "rm", "dd", "mkfs", "shutdown", "reboot", "halt", "poweroff",
    "chmod", "chown", "mount", "umount", "fdisk", "parted",
    "iptables", "ufw", "firewall-cmd", "systemctl",
    "kill", "killall", "pkill", "sudo", "su", "passwd",
    "init", "telinit", "service", "crontab", "at",
}

_BASH_DANGEROUS_KEYWORDS = [
    r'\brm\s+-rf\b', r'\bdd\s+if=', r'/dev/null',
    r'>\s*/dev/', r'>>\s*/etc/', r'\bmkfs\.', r'\bwipefs\b',
]


def _check_dangerous_bash_code(code: str) -> Optional[str]:
    """扫描 bash 代码中的危险命令。"""
    import re as _re
    # 检查关键词模式
    for pattern in _BASH_DANGEROUS_KEYWORDS:
        if _re.search(pattern, code):
            return f"[拒绝] Bash 代码包含危险模式：{_re.search(pattern, code).group(0)[:50]}"
    # 检查危险命令名
    words = set(_re.findall(r'\b(\w+(?:\.\w+)*)', code))
    for cmd in words & _BASH_DANGEROUS_CMDS:
        return f"[拒绝] Bash 代码包含危险命令：{cmd}"
    return None


def _exec_code_run(language: str, code: str, timeout: int = 30) -> str:
    """在受限环境中运行代码，返回 stdout + stderr。

    安全措施：
      1. 扫描危险 pattern（os.system, subprocess, eval, socket 等）
      2. 资源限制（Unix: RLIMIT_CPU/AS；Windows: 仅 timeout）
      3. 建议生产环境使用 Docker 沙箱
    """
    # 安全检查
    danger = _check_dangerous_code(code)
    if danger:
        return danger
    # bash 代码额外检查危险命令（bash -c 等效于 shell=True）
    if language == "bash":
        bash_danger = _check_dangerous_bash_code(code)
        if bash_danger:
            return bash_danger

    cmds = {
        "python": [sys.executable, "-c", code],
        "node":   ["node", "-e", code],
        "bash":   ["bash", "-c", code],
    }
    cmd = cmds.get(language)
    if not cmd:
        return f"[错误] 不支持的语言：{language}"

    # Unix 资源限制
    preexec_fn = None
    if hasattr(os, "setrlimit"):
        import resource as _r
        def _limit():
            try:
                _r.setrlimit(_r.RLIMIT_CPU, (timeout, timeout))
                _r.setrlimit(_r.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))  # 256MB
            except Exception as _:
                pass
        preexec_fn = _limit

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(Path.cwd()), preexec_fn=preexec_fn,
            encoding="utf-8", errors="replace",
        )
        output = []
        if result.stdout:
            output.append(f"stdout:\n{result.stdout[:2000]}")
        if result.stderr:
            output.append(f"stderr:\n{result.stderr[:500]}")
        output.append(f"退出码：{result.returncode}")
        return "\n".join(output) or "（无输出）"
    except subprocess.TimeoutExpired:
        return f"[超时] 代码执行超过 {timeout} 秒"
    except FileNotFoundError:
        return f"[错误] 未安装 {language} 运行环境"


def _exec_file_read(path: str, start_line: int = None,
                    end_line: int = None) -> str:
    """读取文件内容，支持指定行范围。"""
    p = Path(path)
    if not p.exists():
        return f"[错误] 文件不存在：{path}"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        if start_line or end_line:
            s = (start_line or 1) - 1
            e = end_line or len(lines)
            lines = lines[s:e]
            header = f"[{path} 第{s+1}-{min(e,len(lines)+s)}行]\n"
        else:
            header = f"[{path}]\n"
        content = "\n".join(lines)
        if len(content) > 4000:
            content = content[:4000] + f"\n... [截断，共 {len(lines)} 行]"
        return header + content
    except Exception as e:
        return f"[读取错误] {path}: {e}"


def _exec_file_write(path: str, content: str, mode: str = "write") -> str:
    """写入文件，自动创建父目录。强制限制在项目根目录内，防止路径穿越攻击。"""
    cwd = Path.cwd().resolve()
    p = Path(path)
    # 路径穿越防护：解析真实路径后确保在项目目录内
    try:
        target = p.resolve() if p.is_absolute() else (cwd / p).resolve()
        target.relative_to(cwd)
    except ValueError:
        return f"[拒绝] 不允许写入项目目录外的路径：{path}"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_mode = "a" if mode == "append" else "w"
    try:
        with open(target, write_mode, encoding="utf-8") as f:
            f.write(content)
        return f"[写入成功] {path}（{len(content)} 字符）"
    except Exception as e:
        return f"[写入错误] {path}: {e}"


import shlex

def _exec_bash(command: str, timeout: int = 60) -> str:
    """安全执行 shell 命令（不使用 shell=True，防注入）。"""
    # 解析命令为参数列表
    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        return f"[错误] 命令解析失败：{e}"
    if not cmd_parts:
        return "[错误] 空命令"

    # 基础命令白名单检查（第一个参数为可执行文件名）
    base_cmd = cmd_parts[0]
    DANGEROUS = {
        "rm", "dd", "mkfs", "shutdown", "reboot", "halt", "poweroff",
        "chmod", "chown", "mount", "umount", "fdisk", "parted",
        "iptables", "ufw", "firewall-cmd", "systemctl",
        "kill", "killall", "pkill", "sudo", "su", "passwd",
        "init", "telinit", "service", "crontab", "at",
    }
    if base_cmd in DANGEROUS:
        return f"[拒绝] 禁止执行危险命令：{base_cmd}"

    # 限制工作目录在项目根（防止路径遍历）
    cwd = str(Path.cwd().resolve())
    try:
        result = subprocess.run(
            cmd_parts, shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=cwd,
            encoding="utf-8", errors="replace",
        )
        output = []
        if result.stdout:
            output.append(result.stdout[:3000])
        if result.stderr:
            output.append(f"stderr: {result.stderr[:500]}")
        output.append(f"退出码：{result.returncode}")
        return "\n".join(output) or "（无输出）"
    except FileNotFoundError:
        return f"[错误] 命令未找到：{base_cmd}"
    except subprocess.TimeoutExpired:
        return f"[超时] 命令执行超过 {timeout} 秒：{command}"
    except PermissionError:
        return f"[错误] 权限不足：{base_cmd}"


def _exec_diff_view(content_a: str, content_b: str,
                    is_file: bool = False) -> str:
    """对比两段内容或两个文件的差异。"""
    import difflib
    if is_file:
        a_text = Path(content_a).read_text(encoding="utf-8").splitlines() if Path(content_a).exists() else []
        b_text = Path(content_b).read_text(encoding="utf-8").splitlines() if Path(content_b).exists() else []
        label_a, label_b = content_a, content_b
    else:
        a_text = content_a.splitlines()
        b_text = content_b.splitlines()
        label_a, label_b = "原始", "修改后"

    diff = list(difflib.unified_diff(a_text, b_text,
                                      fromfile=label_a, tofile=label_b, n=2))
    if not diff:
        return "两者完全相同，无差异"
    return "\n".join(diff[:100]) + ("\n... [差异过长，已截断]" if len(diff) > 100 else "")
def _exec_resource_search(query: str, category: str = None) -> str:
    """搜索技术知识储备库。"""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from resource_library import search, init_resource_library
        init_resource_library()
        cats = [category] if category else None
        return search(query, top_k=3, categories=cats)
    except Exception as e:
        return f"[知识库查询失败] {e}"


def _exec_api_doc_update(method: str, path: str, summary: str, tag: str,
                          parameters: list = None, request_body: dict = None,
                          responses: dict = None,
                          requires_auth: bool = True) -> str:
    """添加/更新接口定义到 OpenAPI 规范。"""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from doc_generator import add_endpoint, init_api_doc, API_OUTPUT_DIR
        if not (API_OUTPUT_DIR / "openapi.yaml").exists():
            init_api_doc("项目 API")
        add_endpoint(method=method, path=path, summary=summary, tag=tag,
                     parameters=parameters, request_body=request_body,
                     responses=responses, requires_auth=requires_auth)
        return f"✅ 接口已记录：{method} {path}"
    except Exception as e:
        return f"[接口文档更新失败] {e}"




def _exec_ui_ux_search(query: str, domain: str = None, stack: str = None,
                        max_results: int = 3) -> str:
    """执行 UI/UX Pro Max 设计知识库搜索。"""
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent / "ui_ux_pro_max" / "src" / "ui-ux-pro-max" / "scripts"
    search_py = scripts_dir / "search.py"
    if not search_py.exists():
        return "[错误] UI/UX Pro Max 知识库未安装：" + str(search_py)

    cmd = [sys.executable, str(search_py), query, "--json", "--max-results", str(max_results)]
    if stack:
        cmd += ["--stack", stack]
    elif domain:
        cmd += ["--domain", domain]

    try:
        # 注意：Windows 上 text=True 默认用 cp1252 解码，会破坏 UTF-8 输出（含 emoji）
        # 因此手动用 UTF-8 解码 bytes
        result = subprocess.run(cmd, capture_output=True, timeout=30,
                                cwd=str(scripts_dir))
        stdout = result.stdout.decode("utf-8", errors="replace").strip() if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace").strip() if result.stderr else ""
        if result.returncode != 0:
            return "[UI/UX 搜索失败] " + (stderr[:500] or stdout[:500] or f"退出码 {result.returncode}")
        return stdout or "未找到匹配结果"
    except subprocess.TimeoutExpired:
        return "[超时] UI/UX 知识库搜索超时（30s）"
    except Exception as e:
        return "[UI/UX 搜索异常] " + str(e)



# ════════════════════════════════════════════════════
# 系统提示词工具说明生成器
# 自动为每个角色的系统提示词注入工具使用说明
# ════════════════════════════════════════════════════

TOOL_USAGE_HINTS = {
    "web_search":      "查阅库文档、搜索错误解决方案、了解技术规范",
    "code_run":        "运行代码验证逻辑、执行测试、复现 Bug",
    "file_read":       "查看已有代码、读取接口文档、查看配置",
    "file_write":      "将生成的代码/文档保存到 outputs/ 目录",
    "bash":            "执行部署命令、查看日志、运行构建脚本",
    "diff_view":       "对比代码修改前后差异、验证修复效果",
    "resource_search": "搜索项目知识库获取最佳实践、设计模式和安全规范",
    "api_doc_update":  "将接口定义写入 OpenAPI 规范（用于记录 API 设计）",
    "ui_ux_search":    "查询 UI/UX 设计知识库获取风格、配色、字体、UX 准则、图表和模板推荐",
}

def build_tools_prompt(role: str, use_native_format: bool = False,
                       task_context: str = "") -> str:
    """生成注入到系统提示词末尾的工具使用说明。

    参数：
        role: 角色名
        use_native_format: True=原生 function calling 提示（GPT-4o/Codex），
                           False=XML 格式提示（DeepSeek 等 tool calling 弱的模型）
        task_context: 任务描述文本，用于 Tool Loadout 动态筛选
    """
    all_tools = get_tool_names_for_role(role)
    tools = get_tool_names_for_role(role, task_context)
    if not tools:
        return ""

    # 如果有工具被筛掉了，备注一下
    filtered_out = [t for t in all_tools if t not in tools]
    lines = ["\n## 可用工具\n你可以根据任务需要自主调用以下工具，不需要请示就直接用：\n"]
    for t in tools:
        hint = TOOL_USAGE_HINTS.get(t, "")
        lines.append(f"- **{t}**：{hint}")
    if filtered_out:
        lines.append(f"\n（根据当前任务上下文，{', '.join(filtered_out)} 暂不展示，如需使用直接调用即可。这些工具仍可正常执行。）")

    if use_native_format:
        lines.append("")
        lines.append("### 工具调用方式")
        lines.append("你可以使用 API 的原生 function calling 机制调用以下工具。")
        lines.append("系统会自动执行你的工具调用并将结果回传给你。")
        lines.append("当你需要调用工具时，直接使用 function calling 接口即可，不要输出 XML 格式。")
        lines.append("")
        lines.append("重要规则：")
        lines.append("- **file_write**：创建实际代码文件，不要只描述代码结构或输出文本总结")
        lines.append("- **code_run**：代码写完后运行验证，确保能跑通")
        lines.append("- **web_search / resource_search**：不确定的技术细节先搜索")
        lines.append("- **file_read**：查看已有代码和上游输出，避免重复造轮子")
    else:
        lines.append("")
        lines.append("### 工具调用格式（重要）")
        lines.append("当需要使用工具时，请使用以下XML格式（不要输出空`<tool_calls>`标签）：")
        lines.append("")
        lines.append('```')
        lines.append('<invoke name="file_write">')
        lines.append('  <parameter name="path">outputs/silver_demo/app.py</parameter>')
        lines.append('  <parameter name="content">print("hello")</parameter>')
        lines.append('</invoke>')
        lines.append('```')
        lines.append("")
        lines.append("也可以直接使用函数调用的方式输出多个工具：")
        lines.append("每个工具写一个 `<invoke name=\"工具名\">...<parameter name=\"参数名\">参数值</parameter>...</invoke>` 块。")
        lines.append("代码生成任务中，必须使用 file_write 创建实际的源代码文件，不要只描述代码。")
    lines.append("\n工具调用原则：遇到不确定的技术细节先搜索再动手；代码写完先运行验证再输出。")
    return "\n".join(lines)
