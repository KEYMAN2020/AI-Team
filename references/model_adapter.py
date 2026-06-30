"""
model_adapter.py — 模型适配层
==============================
把"角色做什么"（role prompts）和"怎么调模型"（API 参数）彻底分开。

换模型时：只改 ACTIVE_PROVIDER，不碰任何角色提示词或状态文件。

支持的提供商：
  deepseek   → DeepSeek V4 Pro / Flash（兼容 OpenAI SDK）
  claude     → Claude Sonnet / Opus（Anthropic SDK）
  openai     → GPT-4o / o1（OpenAI SDK）
  gemini     → Gemini 1.5 Pro（Google GenAI SDK）
  any        → 任何兼容 OpenAI 格式的本地或第三方模型

切换方式：
  1. 修改下方 ACTIVE_PROVIDER
  2. 设置对应的环境变量（API Key）
  3. 其他代码不需要改动
"""

import os
import re
import sys
import json
import logging
import threading
from typing import Optional

# Safe stderr handler – catches ValueError when stderr is closed in subprocess/asyncio
class _SafeStderrHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except (ValueError, OSError):
            pass  # stderr closed, silently ignore

# 日志：同时输出到 stdout 和 stderr，带时间戳
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[_SafeStderrHandler(sys.stderr)],
)
logger = logging.getLogger("model_adapter")

# 工具注册表（角色绑定的工具列表）
from tools_registry import get_tools_for_role, execute_tool, build_tools_prompt, TOOL_DEFS

# 熔断器（防止 API key 失效时无限重试烧 Token）
from circuit_breaker import get_breaker

# 角色注册表（单一来源，自动发现 roles/*/config.yaml）
from role_registry import (
    get_role_config as _get_role_cfg_from_registry,
    get_role_configs_all_providers as _get_role_configs_all_providers,
    get_role_file_map as _get_role_file_map,
    get_role_prompt as _get_role_prompt,
)

# YAML 配置加载器（优先从 config/ 加载，硬编码作为 fallback）
try:
    from config_loader import (
        get_active_provider as _get_active_provider,
        get_provider_cost as _get_provider_cost,
        get_role_configs as _get_role_configs,
        get_enable_prompt_caching as _get_enable_prompt_caching,
        get_default_timeout as _get_default_timeout,
    )
except ImportError:
    _get_active_provider = None
    _get_provider_cost = None
    _get_role_configs = None
    _get_enable_prompt_caching = None
    _get_default_timeout = None

# ═══════════════════════════════════════════════════
# ★ 切换模型提供商（优先从 config/providers.yaml 读取）
# ═══════════════════════════════════════════════════
ACTIVE_PROVIDER = _get_active_provider("any") if _get_active_provider else "any"

# 默认超时（秒），角色级别可在 ROLE_CONFIGS 中覆盖
DEFAULT_TIMEOUT = _get_default_timeout(180) if _get_default_timeout else 180

# Prompt Caching：重复的 system prompt 自动缓存，减少 token 费用
# Claude 需要显式标记，OpenAI/GPT-4o 自动生效无需配置
ENABLE_PROMPT_CACHING = _get_enable_prompt_caching(True) if _get_enable_prompt_caching else True


# ═══════════════════════════════════════════════════
# 角色 → 模型配置映射
# 基础配置来自 roles/*/config.yaml（role_registry），
# 可由 config/roles.yaml（YAML 覆盖层）覆写。
# 每个 provider 的配置独立，切换 ACTIVE_PROVIDER 自动生效。
# ═══════════════════════════════════════════════════

ROLE_CONFIGS = _get_role_configs_all_providers()
if not ROLE_CONFIGS:
    logger.warning("ROLE_CONFIGS 为空！role_registry 可能未发现任何角色配置，"
                   "所有 API 调用将使用硬编码 fallback。")


# ── 如果 config/roles.yaml 存在，用它覆盖角色注册表配置 ──
if _get_role_configs:
    try:
        _yaml_roles = _get_role_configs()
        if _yaml_roles:
            for _provider, _roles in _yaml_roles.items():
                if _provider in ROLE_CONFIGS:
                    ROLE_CONFIGS[_provider].update(_roles)
                else:
                    ROLE_CONFIGS[_provider] = _roles
    except Exception:
        pass  # YAML 加载失败，保持角色注册表配置

# ═══════════════════════════════════════════════════
# Token 用量追踪
# ═══════════════════════════════════════════════════

_token_usage: list[dict] = []
_usage_lock = threading.Lock()

# 各提供商 token 单价（美元/1K tokens，仅供参考）
PROVIDER_COST_PER_1K = {
    "deepseek":   {"input": 0.002,  "output": 0.008},
    "claude":     {"input": 0.003,  "output": 0.015},
    "openai":     {"input": 0.005,  "output": 0.015},
    "gemini":     {"input": 0.00125, "output": 0.005},
    "any":        {"input": 0.002,  "output": 0.008},
}

# ── 如果 config/providers.yaml 有价格数据，覆盖 ──
if _get_provider_cost:
    try:
        _yaml_costs = _get_provider_cost()
        if _yaml_costs:
            PROVIDER_COST_PER_1K.update(_yaml_costs)
    except Exception:
        pass

def record_usage(role: str, provider: str, model: str,
                 prompt_tokens: int, completion_tokens: int) -> None:
    """线程安全地记录一次 API 调用的 token 用量。"""
    if not prompt_tokens and not completion_tokens:
        return
    with _usage_lock:
        _token_usage.append({
            "role": role,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
            "total_tokens": (prompt_tokens or 0) + (completion_tokens or 0),
        })

def get_token_usage() -> list[dict]:
    with _usage_lock:
        return list(_token_usage)

def reset_token_usage() -> None:
    with _usage_lock:
        _token_usage.clear()

def compute_usage_summary() -> dict:
    """
    汇总 token 用量，按角色和提供商分组，计算预估费用。
    """
    records = get_token_usage()
    total_prompt = sum(r["prompt_tokens"] for r in records)
    total_completion = sum(r["completion_tokens"] for r in records)
    total_tokens = total_prompt + total_completion

    by_role: dict = {}
    by_provider: dict = {}
    for r in records:
        role = r["role"] or "unknown"
        p = r["provider"]
        by_role.setdefault(role, {"calls": 0, "tokens": 0})
        by_role[role]["calls"] += 1
        by_role[role]["tokens"] += r["total_tokens"]
        by_provider.setdefault(p, {"calls": 0, "tokens": 0})
        by_provider[p]["calls"] += 1
        by_provider[p]["tokens"] += r["total_tokens"]

    # 估算费用（按最后一次调用时的 provider 模型计算，粗略合计）
    total_cost = 0.0
    for r in records:
        costs = PROVIDER_COST_PER_1K.get(r["provider"], PROVIDER_COST_PER_1K["any"])
        total_cost += (r["prompt_tokens"] / 1000) * costs["input"]
        total_cost += (r["completion_tokens"] / 1000) * costs["output"]

    return {
        "total_calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "by_role": by_role,
        "by_provider": by_provider,
    }


# ═══════════════════════════════════════════════════
# 获取角色超时
# ═══════════════════════════════════════════════════

def get_role_timeout(role: str, provider: Optional[str] = None) -> int:
    """
    返回指定角色在当前提供商下的超时时间（秒）。
    优先从 role_registry 读取，未配置则返回 DEFAULT_TIMEOUT。
    """
    p = provider or ACTIVE_PROVIDER
    cfg = _get_role_cfg_from_registry(role, p, default={})
    return cfg.get("timeout", DEFAULT_TIMEOUT) if cfg else DEFAULT_TIMEOUT


# ═══════════════════════════════════════════════════
# 统一调用接口
# ═══════════════════════════════════════════════════

def call_role(role: str, system_prompt: str, user_message: str,
              provider: Optional[str] = None) -> str:
    """
    统一调用入口，自动携带该角色的工具列表。
        output = call_role("frontend", system_prompt, context)
    """
    # 熔断器检查：如果已打开，直接拒绝，不发 HTTP 请求
    breaker = get_breaker()
    if breaker.is_open():
        raise RuntimeError(
            f"API 调用被熔断器拒绝（角色={role}）。\n"
            + breaker.reason()
        )

    p   = provider or ACTIVE_PROVIDER
    cfg = ROLE_CONFIGS.get(p, {}).get(role, {"model": "gpt-4o", "temperature": 0.7})

    try:
        if p == "deepseek":
            result = _call_deepseek(system_prompt, user_message, cfg, role)
        elif p == "claude":
            result = _call_claude(system_prompt, user_message, cfg, role)
        elif p == "openai":
            result = _call_openai(system_prompt, user_message, cfg, role)
        elif p == "gemini":
            result = _call_gemini(system_prompt, user_message, cfg, role)
        else:
            result = _call_openai_compat(system_prompt, user_message, cfg, role)
        breaker.record_success(role)
        return result
    except Exception as e:
        breaker.record_failure(role, str(e))
        raise


# ═══════════════════════════════════════════════════
# Provider 实现
# ═══════════════════════════════════════════════════

def _require_env(key: str, provider_name: str) -> str:
    """获取必需的环境变量，缺失时给出友好提示而非 KeyError。"""
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"缺少环境变量 {key}，无法使用 {provider_name} 提供商。\n"
            f"  请设置：export {key}=\"your-api-key\"\n"
            f"  或切换模型：修改 model_adapter.py 中的 ACTIVE_PROVIDER"
        )
    return val


def _call_deepseek(system: str, user: str, cfg: dict, role: str = "") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=_require_env("DEEPSEEK_API_KEY", "DeepSeek"), base_url="https://api.deepseek.com")
    tools = _to_openai_tools(get_tools_for_role(role)) if role else []
    messages = [{"role":"system","content":system}, {"role":"user","content":user}]
    kwargs = dict(model=cfg["model"], temperature=cfg["temperature"], max_tokens=16384, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if cfg.get("thinking"):
        kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": 2000}}
    if cfg.get("text_tool_compat"):
        kwargs["text_tool_compat"] = True
        kwargs["_role"] = role
        kwargs["_max_iter"] = 8  # DeepSeek 需要更多迭代才能收敛
    try:
        resp = _run_tool_loop_openai(client, kwargs)
    except Exception as e:
        if cfg.get("thinking") and "thinking" in str(e).lower():
            logger.warning("DeepSeek thinking 模式失败，降级为普通模式：%s", e)
            kwargs.pop("extra_body", None)
            resp = _run_tool_loop_openai(client, kwargs)
        else:
            raise
    # 记录 Token 用量
    if hasattr(resp, "usage") and resp.usage:
        record_usage(role, "deepseek", cfg["model"],
                     resp.usage.prompt_tokens, resp.usage.completion_tokens)
    raw = resp.choices[0].message.content or ""
    # ── DSML 归一化：DeepSeek 会在 XML 中插入 U+FF5C 标记──
    raw = raw.replace('\uff5c\uff5cDSML\uff5c\uff5c', '')
    # ── 后处理：清理残留的 <invoke> 标签（DeepSeek fallback 后仍可能产生）──
    # 用正则检测（比 'in' 更可靠，处理特殊 Unicode 字符）
    if _INVOKE_BLOCK_RE.search(raw) or '<invoke' in raw or 'invoke name' in raw:
        cleaned = _strip_invoke_tags(raw)
        if cleaned != raw:
            logger.info("POST_CLEANUP role=%s: stripped invoke tags, len %d → %d", role, len(raw), len(cleaned))
        return cleaned
    return raw


def _call_claude(system: str, user: str, cfg: dict, role: str = "") -> str:
    import anthropic
    headers = {}
    if ENABLE_PROMPT_CACHING:
        headers["anthropic-beta"] = "prompt-caching-2024-07-31"
    client = anthropic.Anthropic(api_key=_require_env("ANTHROPIC_API_KEY", "Claude"),
                                 extra_headers=headers)
    tools = _to_anthropic_tools(get_tools_for_role(role)) if role else []
    # Prompt Caching：在 system prompt 上标记 ephemeral 缓存
    system_prompt = system
    if ENABLE_PROMPT_CACHING:
        system_prompt = [{"type": "text", "text": system,
                          "cache_control": {"type": "ephemeral"}}]
    kwargs = dict(model=cfg["model"], max_tokens=4096,
                  system=system_prompt, messages=[{"role":"user","content":user}])
    if tools:
        kwargs["tools"] = tools
    if cfg.get("thinking"):
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": cfg.get("budget", 2000)}
    else:
        kwargs["temperature"] = cfg["temperature"]
    resp = _run_tool_loop_claude(client, kwargs)
    # 记录 Token 用量
    if hasattr(resp, "usage") and resp.usage:
        record_usage(role, "claude", cfg["model"],
                     resp.usage.input_tokens, resp.usage.output_tokens)
    # 从 content blocks 中提取文本
    texts = [b.text for b in resp.content if hasattr(b, "text")]
    return "\n".join(texts)


def _call_openai(system: str, user: str, cfg: dict, role: str = "") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=_require_env("OPENAI_API_KEY", "OpenAI"))
    model = cfg["model"]
    tools = _to_openai_tools(get_tools_for_role(role)) if role else []
    if model.startswith("o"):
        # o1/o3 系列：不支持 system、temperature、tools/function calling
        messages = [{"role":"developer","content":system}, {"role":"user","content":user}]
        kwargs = {"model": model, "messages": messages,
                  "max_completion_tokens": 4096}
        resp = client.chat.completions.create(**kwargs)
        if hasattr(resp, "usage") and resp.usage:
            record_usage(role, "openai", model,
                         resp.usage.prompt_tokens, resp.usage.completion_tokens)
        return resp.choices[0].message.content or ""
    messages = [{"role":"system","content":system}, {"role":"user","content":user}]
    kwargs = dict(model=model, temperature=cfg["temperature"], max_tokens=4096, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = _run_tool_loop_openai(client, kwargs)
    if hasattr(resp, "usage") and resp.usage:
        record_usage(role, "openai", model,
                     resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return resp.choices[0].message.content or ""


def _call_gemini(system: str, user: str, cfg: dict, role: str = "") -> str:
    import google.generativeai as genai
    from google.generativeai.types import Tool, FunctionDeclaration
    genai.configure(api_key=_require_env("GEMINI_API_KEY", "Gemini"))
    # 转换工具为 Gemini 格式
    tools = _to_gemini_tools(get_tools_for_role(role)) if role else []
    model = genai.GenerativeModel(
        model_name    = cfg["model"],
        system_instruction = system,
        generation_config  = {"temperature": cfg["temperature"], "max_output_tokens": 4096},
        tools = tools or None,
    )
    resp = _run_tool_loop_gemini(model, user, role, cfg)
    # 记录 Token 用量
    if hasattr(resp, "usage_metadata") and resp.usage_metadata:
        record_usage(role, "gemini", cfg["model"],
                     getattr(resp.usage_metadata, "prompt_token_count", 0),
                     getattr(resp.usage_metadata, "candidates_token_count", 0))
    return resp.text


def _call_openai_compat(system: str, user: str, cfg: dict, role: str = "") -> str:
    """兼容 OpenAI 格式的任意端点（本地 Ollama、第三方代理等）。

    注意：如果 text_tool_compat=True，不会向 API 发送 tools 参数，
    （部分端点如 Codex 不支持 tool_calls），而是通过 text_tool_compat
    解析模型文本输出中的工具调用意图。"""
    from openai import OpenAI
    # 调试：检查当前环境是否有代理变量干扰
    for _pv in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        if os.environ.get(_pv):
            logger.info("PROXY_DEBUG _call_openai_compat: %s=%s", _pv, os.environ[_pv])
    client = OpenAI(
        api_key  = os.environ.get("AI_TEAM_API_KEY", "sk-dummy"),
        base_url = os.environ.get("AI_TEAM_BASE_URL", "http://localhost:11431/v1"),
        timeout  = 300,  # 5 分钟，大上下文需要更长时间
        # 覆盖 SDK 默认的 User-Agent "OpenAI/Python x.y"，否则 gsykj.com 会返回 403
        default_headers = {"User-Agent": "ai-team/1.0"},
    )
    tools = _to_openai_tools(get_tools_for_role(role)) if role else []
    messages = [{"role":"system","content":system}, {"role":"user","content":user}]
    kwargs = dict(model=cfg["model"], temperature=cfg.get("temperature", 0.7),
                  max_tokens=4096, messages=messages)
    text_compat = cfg.get("text_tool_compat", False)
    if cfg.get("_max_iter"):
        kwargs["_max_iter"] = cfg["_max_iter"]
    if text_compat:
        # text_tool_compat 模式：不发 tools 给 API，只在内部分析文本
        kwargs["text_tool_compat"] = True
        kwargs["_role"] = role
        kwargs["_available_tools"] = tools  # 给文本解析器用，不会发到 API
    elif tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = _run_tool_loop_openai(client, kwargs)
    if hasattr(resp, "usage") and resp.usage:
        record_usage(role, "any", cfg["model"],
                     resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return resp.choices[0].message.content or ""


# ═══════════════════════════════════════════════════
# ★ 文本工具调用兼容层（Text-based Tool Call Compatibility）
# ═══════════════════════════════════════════════════
# 部分模型（如 DeepSeek）的 function calling 能力弱，经常把工具调用意图
# 输出为纯文本而非 structured tool_calls。本兼容层在 OpenAI 协议路径上
# 做兜底：当 msg.tool_calls 为空时，尝试从 msg.content 中解析文本形式的
# 工具调用，转成真正的 tool 执行。
#
# 启用方式：在角色 config.yaml 中设置 text_tool_compat: true
#   deepseek:
#     backend:
#       model: deepseek-chat
#       text_tool_compat: true   # ← 开启文本工具调用兼容

_TEXT_TOOL_PATTERN = re.compile(
    r'\b(' + '|'.join(TOOL_DEFS.keys()) + r')\s*\(\s*',
    re.IGNORECASE
)

# ── <invoke> 标签清理正则（后处理用）──
_INVOKE_BLOCK_RE = re.compile(
    r'\s*<invoke\s[^>]*>.*?</invoke\s*>\s*',
    re.DOTALL | re.IGNORECASE
)


def _strip_invoke_tags(text: str) -> str:
    """移除文本中残留的 <invoke> XML 标签块，保留其他文本。

    用于 DeepSeek fallback 后的输出清理 —— 模型可能在纯文本
    响应中嵌入未执行的工具调用。"""
    if not text:
        return text
    # 先删除完整匹配的 <invoke>...</invoke> 块
    cleaned = _INVOKE_BLOCK_RE.sub('\n', text)
    # 再清理可能残留的孤立 <invoke> 开头（截断的标签）
    cleaned = re.sub(r'<invoke[^>]*>[\s\S]*', '', cleaned)
    # 清理多余的空白行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()

def _parse_text_tool_calls(content: str, available_tools: list[str]) -> list[dict]:
    """从纯文本响应中尝试解析工具调用意图。

    支持的格式（按优先级，每种格式一个独立解析器）：
    0. XML 标签格式: <invoke name="tool"><parameter name="k">v</parameter></invoke>
    1. 函数调用语法: file_write(path="x", content="y")
    2. 代码块包裹: ```file_write\n{"path":"x","content":"y"}\n```
    3. 键值对形式: path: outputs/main.py \n content: |-\n   ...

    返回: [{"name": "file_write", "arguments": {...}}, ...]
    """
    if not content or not available_tools:
        return []

    # DeepSeek fallback 标记清理
    _DSML_MARKER = '\uff5c\uff5cDSML\uff5c\uff5c'
    content = content.replace(_DSML_MARKER, '')

    # 预处理：提取 <tool_calls> 包裹内的实际内容
    content = _extract_tool_calls_wrapper(content)
    if content is None:  # 空的 <tool_calls> 标签
        return []

    # 按优先级尝试各格式（early return：命中了就返回）
    parsers = [
        _parse_xml_invoke_format,
        _parse_function_call_format,
        _parse_codeblock_format,
        _parse_kv_format,
    ]
    for parser in parsers:
        results = parser(content, available_tools)
        if results:
            return results

    return []


def _extract_tool_calls_wrapper(content: str) -> str | None:
    """提取 <tool_calls> 包裹内的实际内容。返回 None 表示空标签。"""
    tc_m = re.search(r'<tool_calls[^>]*>([\s\S]*?)</tool_calls\s*>', content, re.IGNORECASE)
    if not tc_m:
        return content
    inner = tc_m.group(1).strip()
    return inner if inner else None


def _parse_xml_invoke_format(content: str, available_tools: list[str]) -> list[dict]:
    """格式0: XML 标签格式 — <invoke name="tool"><parameter name="k">v</parameter></invoke>"""
    if '<invoke ' not in content and '<invoke>' not in content:
        return []

    import xml.etree.ElementTree as ET
    results = []

    # 优先用 XML 解析
    try:
        wrapped = f"<root>{content}</root>"
        wrapped = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', wrapped)
        root = ET.fromstring(wrapped)
        for inv in root.findall('.//invoke'):
            tool_name = inv.get('name', '')
            if tool_name not in available_tools:
                continue
            args = {}
            for param in inv.findall('parameter'):
                pname = param.get('name', '')
                pval = param.get('value')
                if pval is None:
                    pval = (param.text or '').strip()
                if pname:
                    args[pname] = pval
            if args:
                results.append({"name": tool_name, "arguments": args})
    except ET.ParseError:
        # XML 解析失败 → 正则 fallback
        return _parse_xml_regex_fallback(content, available_tools)

    return results


def _parse_xml_regex_fallback(content: str, available_tools: list[str]) -> list[dict]:
    """XML 解析失败时的正则 fallback。"""
    results = []
    invoke_re = re.compile(
        r'<invoke\s+name\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)(?:</invoke\s*>|$)',
        re.DOTALL | re.IGNORECASE
    )
    for m in invoke_re.finditer(content):
        tool_name = m.group(1)
        if tool_name not in available_tools:
            continue
        body = m.group(2)
        args = {}
        param_re = re.compile(
            r'<parameter\s+name\s*=\s*["\']([^"\']+)["\'](?:\s+value\s*=\s*["\']([^"\']*)["\'])?[^>]*>(.*?)(?:</parameter\s*>|$)',
            re.DOTALL | re.IGNORECASE
        )
        param_simple_re = re.compile(
            r'<parameter\s+name\s*=\s*["\']([^"\']+)["\']\s+value\s*=\s*["\']([^"\']*)["\']\s*/>',
            re.DOTALL | re.IGNORECASE
        )
        for pm in param_re.finditer(body):
            pname = pm.group(1)
            pval = pm.group(2)
            if pval is None:
                pval = (pm.group(3) or '').strip()
            if pname:
                args[pname] = pval
        for pm in param_simple_re.finditer(body):
            pname = pm.group(1)
            pval = pm.group(2) or ''
            if pname and pname not in args:
                args[pname] = pval
        if args:
            results.append({"name": tool_name, "arguments": args})
    return results


def _parse_function_call_format(content: str, available_tools: list[str]) -> list[dict]:
    """格式1: 函数调用语法 — file_write(path="x", content="y")"""
    results = []
    for tool in available_tools:
        m = re.search(rf'\b{re.escape(tool)}\s*\(\s*', content, re.IGNORECASE)
        if not m:
            continue
        paren_start = m.end()
        depth = 1
        i = paren_start
        in_single = in_double = False
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == '\\':
                i += 2
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "'" and not in_double:
                in_single = not in_single
            elif not in_single and not in_double:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
            i += 1
        if depth == 0:
            args_str = content[paren_start:i - 1].strip()
            args = _parse_args_string(args_str)
            if args:
                if tool in ('code_run', 'bash') and 'code' not in args:
                    code_block = _extract_code_block(content, i)
                    if code_block:
                        args['code'] = code_block
                results.append({"name": tool, "arguments": args})
                break
    return results


def _parse_codeblock_format(content: str, available_tools: list[str]) -> list[dict]:
    """格式2: 代码块格式 — ```file_write\n{"path":"x","content":"..."}\n```"""
    results = []
    import json as _json
    for tool in available_tools:
        block_m = re.search(
            rf'```\s*{re.escape(tool)}\s*\n(.+?)\n\s*```',
            content, re.IGNORECASE | re.DOTALL
        )
        if block_m:
            payload = block_m.group(1).strip()
            try:
                args = _json.loads(payload)
                results.append({"name": tool, "arguments": args})
                break
            except _json.JSONDecodeError:
                pass
    return results


def _parse_kv_format(content: str, available_tools: list[str]) -> list[dict]:
    """格式3: 结构化键值对 — 检测工具名提及和关键参数。"""
    from tools_registry import TOOL_DEFS
    results = []
    for tool in available_tools:
        if tool not in content.lower():
            continue
        tool_def = TOOL_DEFS.get(tool, {})
        params = _extract_kv_params(content, tool_def)
        if params:
            results.append({"name": tool, "arguments": params})
            break
    return results


def _parse_args_string(args_str: str) -> dict:
    """解析函数调用参数字符串。
    支持: key="value", key='value', key=123, 以及多行值的 Python 风格字符串。"""
    if not args_str.strip():
        return {}
    import json as _json
    # 先尝试当作 JSON 解析 {"key": "value"}
    if args_str.strip().startswith('{'):
        try:
            return _json.loads(args_str)
        except _json.JSONDecodeError:
            pass

    result = {}
    # 匹配 key=value 对：key="val" | key='val' | key=数字 | key=布尔
    kv = re.compile(
        r'(\w+)\s*=\s*'
        r'("(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r'|[^\s,)]+)',
        re.DOTALL
    )
    for m in kv.finditer(args_str):
        key = m.group(1)
        raw  = m.group(2).strip()
        # 去引号
        if (raw.startswith('"') and raw.endswith('"')) or \
           (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
            # 基本的转义处理
            raw = raw.replace('\\"', '"').replace("\\'", "'").replace('\\n', '\n')
        elif raw.lower() == 'true':
            raw = True
        elif raw.lower() == 'false':
            raw = False
        elif raw.isdigit():
            raw = int(raw)
        result[key] = raw
    return result


def _extract_code_block(content: str, after_pos: int = 0) -> str | None:
    """从内容中提取代码块（```...``` 或缩进块）。"""
    m = re.search(r'```(?:\w*\n)?(.+?)```', content[after_pos:], re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_kv_params(content: str, tool_def: dict) -> dict | None:
    """从结构化文本中提取工具参数（key: value 格式）。"""
    props = tool_def.get("parameters", {}).get("properties", {})
    if not props:
        return None

    result = {}
    for param_name in props:
        # 匹配: param_name: 后面跟的值（到下一个参数或文末）
        m = re.search(
            rf'(?:^|\n)\s*{re.escape(param_name)}\s*[:：]\s*(.+?)(?=\n\s*\w+\s*[:：]|\n\s*```|\Z)',
            content, re.IGNORECASE | re.DOTALL
        )
        if m:
            val = m.group(1).strip()
            # 去引号
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            # 如果值以 |> 或 |- 开始，取后面的代码块
            if val.startswith('|') and len(val) > 1:
                val = val[1:].strip()
            # 如果值看起来是代码块引用
            if val in ('', '...', '略'):
                # 尝试取后面的代码块
                code = _extract_code_block(content, m.start())
                if code:
                    val = code
            result[param_name] = val

    # 至少需要一个 required 参数才返回
    required = tool_def.get("parameters", {}).get("required", [])
    if required and not any(r in result for r in required):
        return None
    return result if result else None


# ═══════════════════════════════════════════════════
# 工具格式转换与 Tool Loop（由 tools_registry 提供工具定义）
# ═══════════════════════════════════════════════════

def _to_openai_tools(tools: list) -> list:
    """将内部工具定义转为 OpenAI function calling 格式。
    内部格式: {name, description, parameters}
    OpenAI:   {"type": "function", "function": {name, description, parameters}}"""
    wrapped = []
    for t in tools:
        wrapped.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
        })
    return wrapped

def _to_anthropic_tools(tools: list) -> list:
    """将内部工具定义转为 Anthropic tools 格式。
    内部格式: {name, description, parameters}
    Anthropic:{name, description, input_schema}"""
    converted = []
    for t in tools:
        converted.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })
    return converted

def _to_gemini_tools(tools: list) -> list:
    """将内部工具定义转为 Google Gemini tools 格式。
    内部格式: {name, description, parameters}
    Gemini: google.generativeai.types.Tool"""
    from google.generativeai.types import Tool, FunctionDeclaration
    if not tools:
        return []
    declarations = []
    for t in tools:
        declarations.append(FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        ))
    return [Tool(function_declarations=declarations)]

def _run_tool_loop_openai(client, kwargs: dict, max_iter: int = 5):
    """调用 OpenAI/DeepSeek chat completion，自动处理 tool_calls 多轮循环。

    每轮：发送请求 → 检测 tool_calls → 执行工具 → 回传 tool_result → 继续
    直到模型返回纯文本或达到 max_iter 上限。

    当 text_tool_compat=True 且 msg.tool_calls 为空时，自动从 msg.content
    中解析文本形式的工具调用（兼容 DeepSeek 等 tool calling 弱的模型）。"""
    import json as _json_mod
    text_compat = kwargs.pop("text_tool_compat", False)
    _role = kwargs.pop("_role", "")
    _available_tools = kwargs.pop("_available_tools", None)
    max_iter = kwargs.pop("_max_iter", max_iter)

    for iteration in range(max_iter):
        resp = _api_call_with_logging(client, kwargs, _role, iteration)
        msg = resp.choices[0].message

        # ── 正常路径：模型返回了 structured tool_calls ──
        if msg.tool_calls:
            _handle_structured_tool_calls(kwargs, msg)
            logger.info("Tool loop iter %d: executed %d tool(s)", iteration + 1, len(msg.tool_calls))
            continue

        # ── 兼容路径：text_tool_compat 开启，尝试从文本解析工具调用 ──
        _avail = _available_tools or kwargs.get("tools")
        if text_compat and msg.content and _avail:
            if _try_text_compat_tool_calls(kwargs, msg, _avail, _role, iteration):
                continue

        # 既无 tool_calls 也无文本工具调用 → 返回最终响应
        rc = resp.choices[0].message.content or ''
        logger.info("NORMAL_RETURN role=%s iter=%d has_invoke=%s content_len=%d", _role, iteration+1, '<invoke' in rc, len(rc))
        return resp

    # 达到最大迭代次数 → fallback
    return _run_fallback_after_max_iter(client, kwargs, _role, _available_tools, text_compat)


def _api_call_with_logging(client, kwargs: dict, _role: str, iteration: int):
    """执行 API 调用并记录详细错误链。"""
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as _api_err:
        logger.error("API_CALL_FAILED role=%s iter=%d error=%s: %s",
                     _role, iteration+1, type(_api_err).__name__, _api_err)
        for attr in ('__cause__', '__context__'):
            cause = getattr(_api_err, attr, None)
            if cause:
                logger.error("API_CALL_%s: %s: %s", attr.upper().strip('_'),
                             type(cause).__name__, cause)
        raise


def _handle_structured_tool_calls(kwargs: dict, msg):
    """处理模型返回的 structured tool_calls，追加对话并执行工具。"""
    import json as _json_mod
    d = msg.model_dump()
    # DeepSeek reasoning_content 不在 model_dump 中，需手动保留
    if 'reasoning_content' not in d:
        rc = getattr(msg, 'reasoning_content', None) or (msg.model_extra or {}).get('reasoning_content', None)
        if rc:
            d['reasoning_content'] = rc
    kwargs["messages"].append(d)
    for tc in msg.tool_calls:
        try:
            args = _json_mod.loads(tc.function.arguments)
        except _json_mod.JSONDecodeError:
            args = {}
        result = execute_tool(tc.function.name, args)
        kwargs["messages"].append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })


def _try_text_compat_tool_calls(kwargs: dict, msg, _avail, _role: str, iteration: int) -> bool:
    """尝试从文本格式解析工具调用。返回 True 表示成功解析并处理了工具。"""
    import json as _json_mod
    import uuid as _uuid
    available = _resolve_tool_names(_avail)
    text_tools = _parse_text_tool_calls(msg.content, available)
    if not text_tools:
        return False
    logger.info(
        "Text compat iter %d: parsed %d tool(s) from text → %s",
        iteration + 1, len(text_tools),
        [t["name"] for t in text_tools]
    )
    stc_list = _build_synthetic_tool_calls(text_tools, "text_compat")
    # DeepSeek 需要保留 reasoning_content 才能做多轮对话
    reasoning_content = getattr(msg, 'reasoning_content', None) or (msg.model_extra or {}).get('reasoning_content', None)
    asst_msg = {
        "role": "assistant",
        "content": msg.content,
        "tool_calls": stc_list,
    }
    if reasoning_content:
        asst_msg["reasoning_content"] = reasoning_content
    kwargs["messages"].append(asst_msg)
    for tt, stc in zip(text_tools, stc_list):
        result = execute_tool(tt["name"], tt["arguments"])
        kwargs["messages"].append({
            "role": "tool",
            "tool_call_id": stc["id"],
            "content": result,
        })
    return True


def _run_fallback_after_max_iter(client, kwargs: dict, _role: str, _available_tools, text_compat: bool):
    """达到最大迭代次数后，去掉 tools 强制模型给出文本回复。"""
    import json as _json_mod
    import uuid as _uuid2

    logger.info("MAX_ITER reached for %s: text_compat=%s, attempting fallback", _role, text_compat)
    final_kwargs = {k: v for k, v in kwargs.items()
                    if k not in ("tools", "tool_choice")}
    final_resp = client.chat.completions.create(**final_kwargs)
    fc = final_resp.choices[0].message.content or ''
    has_invoke = _INVOKE_BLOCK_RE.search(fc) is not None or '<invoke' in fc or 'invoke name' in fc
    logger.info("FALLBACK response for %s: has_invoke=%s, len=%d, preview=%s",
                _role, has_invoke, len(fc), fc[:200])

    if text_compat and has_invoke:
        available = _resolve_tool_names(_available_tools or kwargs.get("tools", []))
        text_tools = _parse_text_tool_calls(fc, available)
        logger.info("FALLBACK parse result for %s: parsed=%d tools, available=%s",
                    _role, len(text_tools), available)
        if text_tools:
            final_resp = _retry_after_fallback_parse(client, final_kwargs, kwargs, fc,
                                                     text_tools, available, _role, _available_tools)
        else:
            _write_fallback_debug(fc, _role)
    else:
        if text_compat:
            logger.info("FALLBACK no-invoke: text_compat=True but no <invoke> in response for %s", _role)
    return final_resp


def _retry_after_fallback_parse(client, final_kwargs, kwargs, fc, text_tools, available, _role, _available_tools):
    """Fallback 解析出工具调用后，构建合成 tool_calls 并重新执行工具循环。"""
    import json as _json_mod
    import uuid as _uuid2
    if not _available_tools:
        _orig_tools = kwargs.get("tools", [])
        if _orig_tools:
            final_kwargs["tools"] = _orig_tools
            final_kwargs["tool_choice"] = "auto"
    synthetic_tool_calls = _build_synthetic_tool_calls(text_tools, "fallback")
    final_kwargs["messages"].append({
        "role": "assistant", "content": fc,
        "tool_calls": synthetic_tool_calls,
    })
    for tt, stc in zip(text_tools, synthetic_tool_calls):
        result = execute_tool(tt["name"], tt["arguments"])
        final_kwargs["messages"].append({
            "role": "tool",
            "tool_call_id": stc["id"],
            "content": result,
        })
    # 再试最多 3 轮
    last_resp = None
    for _ in range(3):
        r2 = client.chat.completions.create(**final_kwargs)
        m2 = r2.choices[0].message
        last_resp = r2
        if m2.tool_calls:
            final_kwargs["messages"].append(m2.model_dump())
            for tc in m2.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                r3 = execute_tool(tc.function.name, args)
                final_kwargs["messages"].append({"role": "tool", "tool_call_id": tc.id, "content": r3})
            continue
        # 又碰到文本格式？再解析一次
        if m2.content and '<invoke' in m2.content:
            tt2 = _parse_text_tool_calls(m2.content, available)
            if tt2:
                stc2 = _build_synthetic_tool_calls(tt2, "fb2")
                final_kwargs["messages"].append({"role": "assistant", "content": m2.content, "tool_calls": stc2})
                for tt, stc in zip(tt2, stc2):
                    r3 = execute_tool(tt["name"], tt["arguments"])
                    final_kwargs["messages"].append({"role": "tool", "tool_call_id": stc["id"], "content": r3})
                continue
        return r2
    return last_resp


def _build_synthetic_tool_calls(text_tools: list, prefix: str) -> list:
    """将文本解析的工具调用转为合成 tool_calls 格式。"""
    import json as _json_mod
    import uuid as _uuid
    result = []
    for tt in text_tools:
        tc_id = f"{prefix}_{_uuid.uuid4().hex[:8]}"
        result.append({
            "id": tc_id,
            "type": "function",
            "function": {
                "name": tt["name"],
                "arguments": json.dumps(tt["arguments"], ensure_ascii=False),
            },
        })
    return result


def _resolve_tool_names(tools_list: list) -> list[str]:
    """从工具列表解析出工具名称列表。"""
    return [
        t["function"]["name"] if isinstance(t, dict) and "function" in t else t.get("name", "")
        for t in tools_list
    ]


def _write_fallback_debug(content: str, _role: str):
    """将无法解析的 fallback 输出写入调试文件。"""
    from pathlib import Path
    dbg = Path(__file__).resolve().parent.parent / f"debug_fallback_{_role}.txt"
    with open(dbg, "w", encoding="utf-8") as df:
        df.write(content)
    logger.info("FALLBACK parse-failed for %s: has <invoke> but could not parse any tools. Wrote %d chars to %s. Preview: %s",
                _role, len(content), dbg, content[:200])

def _run_tool_loop_claude(client, kwargs: dict, max_iter: int = 5):
    """调用 Anthropic messages API，自动处理 tool_use 多轮循环。

    每轮：发送请求 → 检测 tool_use → 执行工具 → 回传 tool_result → 继续
    直到 stop_reason 不再是 tool_use 或达到 max_iter 上限。"""
    for iteration in range(max_iter):
        resp = client.messages.create(**kwargs)
        if resp.stop_reason != "tool_use":
            return resp
        tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
        if not tool_use_blocks:
            return resp
        # 把助手消息（含 tool_use blocks）加入对话
        kwargs["messages"].append({"role": "assistant", "content": resp.content})
        # 执行每个工具，构建 tool_result blocks
        tool_results = []
        for tb in tool_use_blocks:
            result = execute_tool(tb.name, tb.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": result,
            })
        kwargs["messages"].append({"role": "user", "content": tool_results})
        logger.info("Tool loop iter %d: executed %d tool(s)", iteration + 1, len(tool_use_blocks))
    # 达到上限，最后请求一次以获取文本输出
    return client.messages.create(**kwargs)

def _run_tool_loop_gemini(model, user_msg: str, role: str, cfg: dict,
                           max_iter: int = 5):
    """调用 Gemini，自动处理 function_calling 多轮循环。
    Gemini 的 functionCall 和 functionResponse 通过 content.parts 传递。"""
    import logging as _log
    _gemini_log = _log.getLogger("model_adapter")
    from google.generativeai.types import Content, Part
    import json as _json_mod

    # 初始用户消息
    contents = [Content(role="user", parts=[Part(text=user_msg)])]

    for iteration in range(max_iter):
        resp = model.generate_content(contents)

        # 检查是否有 function call
        has_fn_call = False
        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    has_fn_call = True
                    break

        if not has_fn_call:
            return resp

        # 构建 assistant 回复（含 function calls）并执行工具
        fn_results = []
        assistant_parts = []
        for part in resp.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                fn = part.function_call
                assistant_parts.append(Part(function_call=fn))
                try:
                    args = dict(fn.args) if fn.args else {}
                except Exception:
                    args = {}
                result = execute_tool(fn.name, args)
                fn_results.append(Part(function_response={
                    "name": fn.name,
                    "response": {"result": result},
                }))
            elif hasattr(part, 'text') and part.text:
                assistant_parts.append(Part(text=part.text))

        contents.append(Content(role="model", parts=assistant_parts))
        contents.append(Content(role="user", parts=fn_results))

        if fn_results:
            _gemini_log.info("Gemini tool loop iter %d: executed %d tool(s)", iteration + 1, len(fn_results))

    # 达到上限，最后发一次不带工具的请求获取文本输出
    final_model = model
    return final_model.generate_content(contents)
# ═══════════════════════════════════════════════════

from pathlib import Path

_ROLES_DIR = Path(__file__).parent / "roles"

# 角色名→prompt 文件映射（别名→文件名），从 role_registry 获取
_ROLE_FILE_MAP = _get_role_file_map()

def load_system_prompt(role: str, task_context: str = "") -> str:
    """
    从角色的 prompt.md 提取系统提示词，并自动追加工具使用说明。
    支持别名（通过 role_registry 解析）。

    根据当前提供商配置自动选择合适的工具调用提示模板：
    - text_tool_compat=True → XML 格式（DeepSeek 等）
    - text_tool_compat=False → 原生 function calling（GPT-4o/Codex 等）

    如果提供了 task_context，会做 Tool Loadout 动态筛选，
    只展示与当前任务最相关的工具。
    """
    prompt = _get_role_prompt(role)
    if not prompt:
        # 角色不存在或 prompt.md 缺失
        logger.warning("无法加载角色 %s 的系统提示词", role)
        return ""
    # 检测当前提供商是否使用原生 function calling
    cfg = ROLE_CONFIGS.get(ACTIVE_PROVIDER, {}).get(role, {})
    use_native = not cfg.get("text_tool_compat", True)
    # 自动追加工具说明（各角色不同），携带任务上下文做动态筛选
    tools_prompt = build_tools_prompt(role, use_native_format=use_native,
                                       task_context=task_context)
    return prompt + tools_prompt if tools_prompt else prompt


# ═══════════════════════════════════════════════════
# 端到端调用示例
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    from state_manager import init_project, build_context, parse_state_update

    # 初始化项目
    init_project("示例项目")

    # 调用产品经理角色
    system  = load_system_prompt("product")
    context = build_context("product", "调研需求并编写用户故事")

    print(f"使用提供商：{ACTIVE_PROVIDER}")
    print(f"模型：{ROLE_CONFIGS[ACTIVE_PROVIDER]['product']['model']}")
    print("调用中...")

    output = call_role("product", system, context)
    parse_state_update("product", "D001", output)

    print("完成。状态已写入 state/master.json")
