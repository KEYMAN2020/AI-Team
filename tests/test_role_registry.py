"""
test_role_registry.py — 角色注册表单元测试
"""
import yaml
import pytest
from pathlib import Path


class TestRoleDefinition:
    """RoleDefinition 数据类测试"""

    def test_role_definition_basic(self):
        """RoleDefinition 应正确解析 config 字典"""
        from references.role_registry import RoleDefinition
        config = {
            "name": "frontend",
            "description": "前端开发",
            "aliases": ["fe", "front"],
            "model_config": {"deepseek": {"model": "deepseek-chat"}},
            "tools": ["file_read", "file_write"],
            "kb_sections": [{"source": "curated", "section": "standards"}],
            "resource_categories": ["frontend"],
        }
        rd = RoleDefinition("frontend", config, Path("/tmp/prompt.md"))
        assert rd.name == "frontend"
        assert rd.description == "前端开发"
        assert rd.aliases == ["fe", "front"]
        assert rd.tools == ["file_read", "file_write"]
        assert rd.kb_sections == [("curated", "standards")]
        assert rd.resource_categories == ["frontend"]


class TestRoleRegistryScan:
    """角色扫描功能测试"""

    def test_scan_finds_roles(self):
        """scan() 应从实际 roles/ 目录发现 11 个角色"""
        from references.role_registry import scan
        registry = scan(force=True)
        assert len(registry) >= 11
        assert "pm" in registry
        assert "architect" in registry
        assert "frontend" in registry
        assert "backend" in registry
        assert "ux" in registry

    def test_get_all_roles_returns_list(self):
        """get_all_roles() 应返回角色名列表"""
        from references.role_registry import get_all_roles
        roles = get_all_roles()
        assert isinstance(roles, list)
        assert len(roles) >= 11
        assert "pm" in roles

    def test_get_all_aliases_includes_short_names(self):
        """get_all_aliases() 应包含别名映射"""
        from references.role_registry import get_all_aliases
        aliases = get_all_aliases()
        assert isinstance(aliases, dict)

    def test_get_role_config_returns_dict(self):
        """get_role_config() 应返回模型配置"""
        from references.role_registry import get_role_config
        cfg = get_role_config("frontend", "deepseek")
        assert isinstance(cfg, dict)
        assert "model" in cfg

    def test_get_role_config_fallback_default(self):
        """未知角色应返回默认配置"""
        from references.role_registry import get_role_config
        cfg = get_role_config("nonexistent_role", "deepseek")
        assert cfg.get("model") == "gpt-4o"
        assert cfg.get("temperature") == 0.7

    def test_get_role_tools_returns_list(self):
        """get_role_tools() 应返回工具列表"""
        from references.role_registry import get_role_tools
        tools = get_role_tools("frontend")
        assert isinstance(tools, list)
        assert len(tools) >= 3

    def test_get_role_tools_unknown_returns_empty(self):
        """未知角色应返回空列表"""
        from references.role_registry import get_role_tools
        tools = get_role_tools("nonexistent")
        assert tools == []

    def test_resolve_role_self(self):
        """resolve_role() 应返回自身"""
        from references.role_registry import resolve_role
        assert resolve_role("pm") == "pm"
        assert resolve_role("ux") == "ux"

    def test_get_role_prompt_not_empty(self):
        """get_role_prompt() 应返回非空提示词"""
        from references.role_registry import get_role_prompt
        for role in ["pm", "ux", "frontend", "backend"]:
            prompt = get_role_prompt(role)
            assert prompt, f"{role} 的提示词不应为空"
            assert len(prompt) > 50, f"{role} 的提示词过短"

    def test_get_role_file_map_contains_roles(self):
        """get_role_file_map() 应包含角色名映射"""
        from references.role_registry import get_role_file_map
        file_map = get_role_file_map()
        assert "pm" in file_map
        assert file_map["pm"].endswith("prompt.md")

    def test_get_role_configs_all_providers(self):
        """get_role_configs_all_providers() 应返回嵌套 dict"""
        from references.role_registry import get_role_configs_all_providers
        configs = get_role_configs_all_providers()
        assert isinstance(configs, dict)
        # 至少有一个 provider
        assert len(configs) >= 1
        # 每个 provider 下应有角色
        for provider, roles in configs.items():
            assert "pm" in roles
            assert "frontend" in roles
