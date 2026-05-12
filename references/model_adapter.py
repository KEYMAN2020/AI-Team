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
import sys
import json
import logging
import threading
from typing import Optional

# 日志：同时输出到 stdout 和 stderr，带时间戳
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("model_adapter")

# 工具注册表（角色绑定的工具列表）
from tools_registry import get_tools_for_role, execute_tool, build_tools_prompt

# ═══════════════════════════════════════════════════
# ★ 唯一需要改的地方：切换模型提供商
# ═══════════════════════════════════════════════════
ACTIVE_PROVIDER = "deepseek"   # "deepseek" | "claude" | "openai" | "gemini" | "any"

# 默认超时（秒），角色级别可在 ROLE_CONFIGS 中覆盖
DEFAULT_TIMEOUT = 180

# Prompt Caching：重复的 system prompt 自动缓存，减少 token 费用
# Claude 需要显式标记，OpenAI/GPT-4o 自动生效无需配置
ENABLE_PROMPT_CACHING = True


# ═══════════════════════════════════════════════════
# 角色 → 模型配置映射
# 每个 provider 的配置独立，切换 ACTIVE_PROVIDER 自动生效
# ═══════════════════════════════════════════════════

# 角色说明：pm=Tech Lead, architect=架构师, frontend=前端,
#           backend=后端, devops=DevOps, debug=Debug工程师, tester=测试
ROLE_CONFIGS = {

    # ── DeepSeek V4 ─────────────────────────────────
    "deepseek": {
        "pm":       {"model": "deepseek-v4-pro",  "temperature": 0.3, "thinking": True,  "timeout": 120},
        "product":  {"model": "deepseek-v4-pro",  "temperature": 0.5, "thinking": False, "timeout": 90},
        "architect":{"model": "deepseek-v4-pro",  "temperature": 0.3, "thinking": True,  "timeout": 120},
        "ux":       {"model": "deepseek-v4-flash", "temperature": 0.7, "thinking": False, "timeout": 90},
        "dba":      {"model": "deepseek-v4-pro",  "temperature": 0.1, "thinking": True,  "timeout": 300},
        "frontend": {"model": "deepseek-v4-pro",  "temperature": 0.0, "thinking": False, "timeout": 300},
        "backend":  {"model": "deepseek-v4-pro",  "temperature": 0.0, "thinking": False, "timeout": 300},
        "reviewer": {"model": "deepseek-v4-pro",  "temperature": 0.0, "thinking": True,  "timeout": 120},
        "devops":   {"model": "deepseek-v4-flash", "temperature": 0.0, "thinking": False, "timeout": 300},
        "debug":    {"model": "deepseek-v4-pro",  "temperature": 0.0, "thinking": True,  "timeout": 300},
        "tester":   {"model": "deepseek-v4-pro",  "temperature": 0.0, "thinking": False, "timeout": 300},
    },

    # ── Claude ──────────────────────────────────────
    "claude": {
        "pm":       {"model": "claude-opus-4-20250514",   "temperature": 0.3, "thinking": True,  "budget": 2000, "timeout": 120},
        "product":  {"model": "claude-sonnet-4-20250514", "temperature": 0.5, "thinking": False, "timeout": 90},
        "architect":{"model": "claude-opus-4-20250514",   "temperature": 0.3, "thinking": True,  "budget": 2000, "timeout": 120},
        "ux":       {"model": "claude-sonnet-4-20250514", "temperature": 0.7, "thinking": False, "timeout": 90},
        "dba":      {"model": "claude-opus-4-20250514",   "temperature": 0.1, "thinking": True,  "budget": 1500, "timeout": 300},
        "frontend": {"model": "claude-sonnet-4-20250514", "temperature": 0.0, "thinking": False, "timeout": 300},
        "backend":  {"model": "claude-sonnet-4-20250514", "temperature": 0.0, "thinking": False, "timeout": 300},
        "reviewer": {"model": "claude-opus-4-20250514",   "temperature": 0.0, "thinking": True,  "budget": 2000, "timeout": 120},
        "devops":   {"model": "claude-sonnet-4-20250514", "temperature": 0.0, "thinking": False, "timeout": 300},
        "debug":    {"model": "claude-opus-4-20250514",   "temperature": 0.0, "thinking": True,  "budget": 2000, "timeout": 300},
        "tester":   {"model": "claude-sonnet-4-20250514", "temperature": 0.0, "thinking": False, "timeout": 300},
    },

    # ── OpenAI ──────────────────────────────────────
    "openai": {
        "pm":       {"model": "o1",     "temperature": 1.0, "timeout": 120},
        "product":  {"model": "gpt-4o", "temperature": 0.5, "timeout": 90},
        "architect":{"model": "o1",     "temperature": 1.0, "timeout": 120},
        "ux":       {"model": "gpt-4o", "temperature": 0.7, "timeout": 90},
        "dba":      {"model": "gpt-4o", "temperature": 0.1, "timeout": 300},
        "frontend": {"model": "gpt-4o", "temperature": 0.2, "timeout": 300},
        "backend":  {"model": "gpt-4o", "temperature": 0.2, "timeout": 300},
        "reviewer": {"model": "gpt-4o", "temperature": 0.0, "timeout": 120},
        "devops":   {"model": "gpt-4o", "temperature": 0.2, "timeout": 300},
        "debug":    {"model": "o1",     "temperature": 1.0, "timeout": 300},
        "tester":   {"model": "gpt-4o", "temperature": 0.2, "timeout": 300},
    },

    # ── Gemini ──────────────────────────────────────
    "gemini": {
        "pm":       {"model": "gemini-2.0-flash-thinking-exp", "temperature": 0.3, "timeout": 120},
        "product":  {"model": "gemini-2.0-flash",              "temperature": 0.5, "timeout": 90},
        "architect":{"model": "gemini-2.0-flash-thinking-exp", "temperature": 0.3, "timeout": 120},
        "ux":       {"model": "gemini-2.0-flash",              "temperature": 0.7, "timeout": 90},
        "dba":      {"model": "gemini-2.0-flash-thinking-exp", "temperature": 0.1, "timeout": 300},
        "frontend": {"model": "gemini-2.0-flash",              "temperature": 0.0, "timeout": 300},
        "backend":  {"model": "gemini-2.0-flash",              "temperature": 0.0, "timeout": 300},
        "reviewer": {"model": "gemini-2.0-flash",              "temperature": 0.0, "timeout": 120},
        "devops":   {"model": "gemini-2.0-flash",              "temperature": 0.0, "timeout": 300},
        "debug":    {"model": "gemini-2.0-flash-thinking-exp", "temperature": 0.0, "timeout": 300},
        "tester":   {"model": "gemini-2.0-flash",              "temperature": 0.0, "timeout": 300},
    },

    # ── 任意兼容 OpenAI 格式的模型 ──────────────────
    "any": {
        "pm":       {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.3, "timeout": 120},
        "product":  {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.5, "timeout": 90},
        "architect":{"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.3, "timeout": 120},
        "ux":       {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.7, "timeout": 90},
        "dba":      {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.1, "timeout": 300},
        "frontend": {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.2, "timeout": 300},
        "backend":  {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.2, "timeout": 300},
        "reviewer": {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.0, "timeout": 120},
        "devops":   {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.2, "timeout": 300},
        "debug":    {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.0, "timeout": 300},
        "tester":   {"model": os.environ.get("AI_TEAM_MODEL", "gpt-4o"), "temperature": 0.2, "timeout": 300},
    },
}


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
    未配置则返回 DEFAULT_TIMEOUT。
    """
    p = provider or ACTIVE_PROVIDER
    cfg = ROLE_CONFIGS.get(p, {}).get(role, {})
    return cfg.get("timeout", DEFAULT_TIMEOUT)


# ═══════════════════════════════════════════════════
# 统一调用接口
# ═══════════════════════════════════════════════════

def call_role(role: str, system_prompt: str, user_message: str,
              provider: Optional[str] = None) -> str:
    """
    统一调用入口，自动携带该角色的工具列表。
        output = call_role("frontend", system_prompt, context)
    """
    p   = provider or ACTIVE_PROVIDER
    cfg = ROLE_CONFIGS.get(p, {}).get(role, {"model": "gpt-4o", "temperature": 0.7})

    if p == "deepseek":
        return _call_deepseek(system_prompt, user_message, cfg, role)
    elif p == "claude":
        return _call_claude(system_prompt, user_message, cfg, role)
    elif p == "openai":
        return _call_openai(system_prompt, user_message, cfg, role)
    elif p == "gemini":
        return _call_gemini(system_prompt, user_message, cfg, role)
    else:
        return _call_openai_compat(system_prompt, user_message, cfg, role)


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
    kwargs = dict(model=cfg["model"], temperature=cfg["temperature"], max_tokens=4096, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if cfg.get("thinking"):
        kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": 2000}}
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
    return resp.choices[0].message.content or ""


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
    """兼容 OpenAI 格式的任意端点（本地 Ollama、第三方代理等）。"""
    from openai import OpenAI
    client = OpenAI(
        api_key  = os.environ.get("AI_TEAM_API_KEY", "sk-dummy"),
        base_url = os.environ.get("AI_TEAM_BASE_URL", "http://localhost:11434/v1"),
    )
    tools = _to_openai_tools(get_tools_for_role(role)) if role else []
    messages = [{"role":"system","content":system}, {"role":"user","content":user}]
    kwargs = dict(model=cfg["model"], temperature=cfg.get("temperature", 0.7),
                  max_tokens=4096, messages=messages)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = _run_tool_loop_openai(client, kwargs)
    if hasattr(resp, "usage") and resp.usage:
        record_usage(role, "any", cfg["model"],
                     resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return resp.choices[0].message.content or ""


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
    直到模型返回纯文本或达到 max_iter 上限。"""
    import json as _json_mod
    for iteration in range(max_iter):
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return resp
        # 把助手消息（含 tool_calls）加入对话
        kwargs["messages"].append(msg.model_dump())
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
        logger.info("Tool loop iter %d: executed %d tool(s)", iteration + 1, len(msg.tool_calls))
    # 达到最大迭代次数，最后发一次请求获取文本输出
    return client.chat.completions.create(**kwargs)

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

import re
from pathlib import Path

_ROLES_DIR = Path(__file__).parent / "roles"
_ROLE_FILE_MAP = {
    "pm":        "pm.md",
    "product":   "product.md",
    "po":        "product.md",
    "architect": "architect.md",
    "arch":      "architect.md",
    "ux":        "ux.md",
    "dba":       "dba.md",
    "frontend":  "frontend.md",
    "fe":        "frontend.md",
    "backend":   "backend.md",
    "be":        "backend.md",
    "reviewer":  "reviewer.md",
    "cr":        "reviewer.md",
    "devops":    "devops.md",
    "ops":       "devops.md",
    "debug":     "debug.md",
    "dbg":       "debug.md",
    "tester":    "tester.md",
    "qa":        "tester.md",
}

def load_system_prompt(role: str) -> str:
    """
    从对应 .md 文件里提取系统提示词，并自动追加该角色的工具使用说明。
    """
    fp = _ROLES_DIR / _ROLE_FILE_MAP[role]
    content = fp.read_text(encoding="utf-8")
    m = re.search(r"```\n([\s\S]+?)\n```", content)
    prompt = m.group(1).strip() if m else re.sub(r"^#+.*\n", "", content, flags=re.MULTILINE).strip()
    # 自动追加工具说明（各角色不同）
    tools_prompt = build_tools_prompt(role)
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
