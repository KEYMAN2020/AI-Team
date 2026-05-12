"""
role_registry.py — 角色注册表（单一来源）
===========================================
扫描 roles/*/config.yaml 自动发现和注册所有角色。

每个角色是一个目录：
  roles/<name>/
    ├── config.yaml   # 角色配置（模型、工具、知识库章节、资源分类）
    ├── prompt.md     # 系统提示词
    └── README.md     # 人类可读的角色说明（可选）

框架启动时 scan() 扫描所有 roles/*/，自动构建所有映射。
加新角色 = 新建一个目录，放 config.yaml + prompt.md，重启即可。

提供：
  get_all_roles()               → list[str]         # 所有角色名
  get_all_aliases()             → dict[str, str]     # 别名→角色名
  get_role_config(role, provider)→ dict              # 角色+provider 配置
  get_role_tools(role)          → list[str]          # 工具名列表
  get_role_kb_sections(role)    → list[(src, sec)]   # 知识库章节
  get_role_resource_cats(role)  → list[str]          # 资源分类
  get_role_prompt(role)         → str                # 系统提示词
  get_role_file_map()           → dict[str, str]     # 角色名→当前可用文件名

YAML 格式（roles/frontend/config.yaml）：
  name: frontend
  description: 前端开发
  aliases: [fe]
  model_config:
    deepseek: {model: deepseek-v4-pro, temperature: 0.0, thinking: false, timeout: 300}
    claude: {model: claude-sonnet-4-20250514, temperature: 0.0, thinking: false, timeout: 300}
    ...
  tools: [web_search, resource_search, code_run, file_read, file_write]
  kb_sections:
    - {source: curated, section: standards}
    - {source: curated, section: gotchas}
    - {source: auto, section: gotchas}
  resource_categories: [frontend, testing, security]
"""

import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

ROLES_DIR = Path(__file__).resolve().parent / "roles"

_logger = logging.getLogger("role_registry")
_cache_lock = threading.Lock()

# 缓存的注册表
_registry: Optional[dict] = None   # role_name → RoleDefinition
_aliases: Optional[dict] = None    # alias → role_name


class RoleDefinition:
    """从 config.yaml 解析的角色定义。"""
    __slots__ = ("name", "description", "aliases", "model_config",
                 "tools", "kb_sections", "resource_categories", "prompt_path")

    def __init__(self, name: str, config: dict, prompt_path: Path):
        self.name = name
        self.description = config.get("description", "")
        self.aliases = config.get("aliases", [])
        self.model_config = config.get("model_config", {})
        self.tools = config.get("tools", [])
        # kb_sections: YAML list of {source, section} → (source, section) tuples
        self.kb_sections = [
            (entry["source"], entry["section"])
            for entry in config.get("kb_sections", [])
        ]
        self.resource_categories = config.get("resource_categories", [])
        self.prompt_path = prompt_path


def scan(force: bool = False) -> dict[str, RoleDefinition]:
    """
    扫描 roles/*/config.yaml，构建角色注册表（带缓存，线程安全）。

    返回 dict: role_name → RoleDefinition
    """
    global _registry, _aliases

    with _cache_lock:
        if _registry is not None and not force:
            return _registry

        _registry = {}
        _aliases = {}

        if not ROLES_DIR.exists():
            _logger.warning(f"角色目录不存在：{ROLES_DIR}")
            return _registry

        for rdir in sorted(ROLES_DIR.iterdir()):
            if not rdir.is_dir():
                continue

            config_path = rdir / "config.yaml"
            if not config_path.exists():
                continue

            try:
                config = _load_role_config(config_path)
            except Exception as e:
                _logger.warning(f"跳过角色 {rdir.name}：config.yaml 加载失败 — {e}")
                continue

            name = config.get("name", rdir.name)
            prompt_path = rdir / "prompt.md"

            role_def = RoleDefinition(name, config, prompt_path)
            _registry[name] = role_def

            # 注册别名
            for alias in config.get("aliases", []):
                _aliases[alias] = name

        if not _registry:
            _logger.warning("未发现任何角色配置（roles/*/config.yaml）")

        return _registry


def _load_role_config(path: Path) -> dict:
    """加载角色的 config.yaml，验证必需字段。"""
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"config.yaml 必须是 dict，got {type(data)}")
    if not isinstance(data.get("model_config"), dict):
        raise ValueError(f"model_config 必须是 dict，got {type(data.get('model_config'))}")
    if not isinstance(data.get("tools"), list):
        data["tools"] = []
    return data


# ── 公开 API ──────────────────────────────────────

def _ensure_scanned():
    """确保注册表已扫描。"""
    if _registry is None:
        scan()

def get_all_roles() -> list[str]:
    """返回所有已注册角色名的列表。"""
    _ensure_scanned()
    return list(_registry.keys())

def get_all_aliases() -> dict[str, str]:
    """返回别名→角色名映射表。"""
    _ensure_scanned()
    return dict(_aliases)

def get_role_file_map() -> dict[str, str]:
    """
    返回 model_adapter 兼容的角色名→文件名映射。
    key 包括角色名和别名，value 是 "name/prompt.md" 路径。
    """
    _ensure_scanned()
    result = {}
    for name, rd in _registry.items():
        rel = f"{name}/prompt.md"
        result[name] = rel
        for alias in rd.aliases:
            result[alias] = rel
    return result

def get_role_config(role: str, provider: str,
                    default: dict = None) -> dict:
    """返回角色在指定 provider 下的配置。自动解析别名。"""
    _ensure_scanned()
    role = resolve_role(role) or role
    if default is None:
        default = {"model": "gpt-4o", "temperature": 0.7, "timeout": 180}
    rd = _registry.get(role)
    if not rd:
        return dict(default)  # 浅拷贝防外部修改
    cfg = rd.model_config.get(provider)
    return dict(cfg) if cfg else dict(default)

def get_role_configs_all_providers() -> dict:
    """
    返回 model_adapter 兼容的 ROLE_CONFIGS 格式：
    {provider: {role: {model, temperature, ...}}}
    """
    _ensure_scanned()
    # 先找出所有 provider
    providers = set()
    for rd in _registry.values():
        providers.update(rd.model_config.keys())

    result = {}
    for p in sorted(providers):
        result[p] = {}
        for name, rd in _registry.items():
            cfg = rd.model_config.get(p)
            if cfg:
                result[p][name] = dict(cfg)
    return result

def get_role_tools(role: str) -> list[str]:
    """返回角色的工具名称列表。自动解析别名。"""
    _ensure_scanned()
    role = resolve_role(role) or role
    rd = _registry.get(role)
    return list(rd.tools) if rd else []

def get_role_kb_sections(role: str) -> list:
    """返回角色的知识库章节列表 [(source, section), ...]。自动解析别名。"""
    _ensure_scanned()
    role = resolve_role(role) or role
    rd = _registry.get(role)
    return list(rd.kb_sections) if rd else []

def get_role_resource_cats(role: str) -> list[str]:
    """返回角色的资源分类列表。自动解析别名。"""
    _ensure_scanned()
    role = resolve_role(role) or role
    rd = _registry.get(role)
    return list(rd.resource_categories) if rd else []

def get_role_prompt(role: str) -> str:
    """
    读取角色的系统提示词（从 roles/<name>/prompt.md）。
    自动解析别名。
    提取 ``` 代码块内的提示词文本，找不到则取全文。
    """
    _ensure_scanned()
    role = resolve_role(role) or role  # 尝试解析别名
    rd = _registry.get(role)
    if not rd or not rd.prompt_path.exists():
        return ""
    content = rd.prompt_path.read_text(encoding="utf-8")
    m = re.search(r"```\r?\n([\s\S]+?)\r?\n```", content)
    if m:
        return m.group(1).strip()
    return re.sub(r"^#+.*\n", "", content, flags=re.MULTILINE).strip()

def resolve_role(name: str) -> Optional[str]:
    """
    解析角色名（支持别名）。
    返回标准角色名，未知则返回 None。
    """
    _ensure_scanned()
    if name in _registry:
        return name
    return _aliases.get(name)
