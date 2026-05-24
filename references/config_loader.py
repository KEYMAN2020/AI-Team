"""
config_loader.py — YAML 配置加载器
====================================
从 config/ 目录加载 YAML 配置，提供向后兼容的 dict 接口。

配置优先级：YAML 文件 > 硬编码 fallback
环境变量中的占位符 ${VAR:-default} 会被自动展开。

用法：
  from config_loader import get_role_configs, get_provider_config, get_workflow_config
  provider_cfg = get_provider_config()   # providers.yaml
  roles = get_role_configs()             # roles.yaml (完整嵌套 dict)
  workflow = get_workflow_config()       # workflow.yaml
"""

import os
import re
import threading
from pathlib import Path
from typing import Optional

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# ── 缓存 ───────────────────────────────────────────

_cache: dict = {}
_cache_lock = threading.Lock()

# ── 环境变量展开 ───────────────────────────────────

_ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')

def _expand_env(value):
    """递归展开字符串中的 ${VAR:-default} 占位符。"""
    if isinstance(value, str):
        def _replacer(m):
            var_name = m.group(1)
            default = (m.group(2) or "").lstrip("-")  # ${VAR:-default} → "default"
            return os.environ.get(var_name, default)
        return _ENV_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


# ── YAML 加载 ──────────────────────────────────────

def _load_yaml(filename: str) -> dict:
    """加载 config/ 目录下的 YAML 文件（带缓存，线程安全）。"""
    with _cache_lock:
        if filename in _cache:
            return _cache[filename]

        filepath = _CONFIG_DIR / filename
        if not filepath.exists():
            _cache[filename] = {}
            return {}

    try:
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except ImportError:
        # 没有 pyyaml 时尝试 JSON（fallback）
        import json
        json_path = filepath.with_suffix(".json")
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            raise RuntimeError(
                "需要安装 pyyaml：pip install pyyaml\n"
                "或将配置文件转为 JSON 格式放在 config/ 目录下。"
            )
    except Exception as e:
        import logging
        logging.getLogger("config_loader").warning("加载配置 %s 失败: %s", filename, e)
        with _cache_lock:
            _cache[filename] = {}
        return {}

    # 展开环境变量
    expanded = _expand_env(data)
    with _cache_lock:
        _cache[filename] = expanded
    return expanded


# ── 公开 API ───────────────────────────────────────

# 角色默认 fallback 配置（当 YAML 不可用时）
_FALLBACK_ROLE = {"model": "gpt-4o", "temperature": 0.7, "timeout": 180}

def get_provider_config() -> dict:
    """返回 providers.yaml 的全部内容。"""
    return _load_yaml("providers.yaml")

def get_active_provider(default: str = "deepseek") -> str:
    """返回当前激活的 provider 名称。"""
    cfg = get_provider_config()
    return cfg.get("active_provider", default)

def get_default_timeout(default: int = 180) -> int:
    """返回全局默认超时。"""
    cfg = get_provider_config()
    return cfg.get("default_timeout", default)

def get_provider_cost() -> dict:
    """返回各 provider 的 token 单价。"""
    cfg = get_provider_config()
    return cfg.get("provider_cost_per_1k", {})

def get_enable_prompt_caching(default: bool = True) -> bool:
    """返回是否启用 Prompt Caching。"""
    cfg = get_provider_config()
    return cfg.get("enable_prompt_caching", default)

def get_role_configs() -> dict:
    """返回 roles.yaml 的完整内容（嵌套 dict，按 provider→role 组织）。"""
    return _load_yaml("roles.yaml")

def get_role_config(role: str, provider: Optional[str] = None) -> dict:
    """返回指定角色在当前 provider 下的配置。"""
    from model_adapter import ACTIVE_PROVIDER  # fallback 硬编码值
    p = provider or get_active_provider(ACTIVE_PROVIDER)
    roles = get_role_configs()
    provider_roles = roles.get(p, {})
    return provider_roles.get(role, _FALLBACK_ROLE)

def get_workflow_config() -> dict:
    """返回 workflow.yaml 的全部内容。"""
    return _load_yaml("workflow.yaml")

def get_workflow_value(key: str, default=None):
    """获取 workflow 配置中的单个值。"""
    cfg = get_workflow_config()
    return cfg.get(key, default)
