"""
test_server_routes.py — 核心模块可导入性检查
"""
import pytest


class TestServerRouting:
    """服务器核心模块导入测试"""

    def test_health_check_module_importable(self):
        """health_check.py 应可导入"""
        from references.health_check import preflight_check
        assert callable(preflight_check)

    def test_event_bus_module_importable(self):
        """event_bus.py 应可导入"""
        from references.event_bus import subscribe, emit
        assert callable(subscribe)
        assert callable(emit)

    def test_circuit_breaker_accessible(self):
        """circuit_breaker 全局实例应可获取"""
        from references.circuit_breaker import get_breaker
        breaker = get_breaker()
        assert breaker is not None

    def test_knowledge_base_importable(self):
        """knowledge_base 模块应可导入"""
        from references.knowledge_base import init_knowledge_base
        assert callable(init_knowledge_base)

    def test_logger_importable(self):
        """logger 模块应可导入"""
        from references.logger import init_logger, get_logger
        assert callable(init_logger)
        assert callable(get_logger)

    def test_config_loader_importable(self):
        """config_loader 模块应可导入"""
        from references.config_loader import get_provider_config, get_role_configs
        assert callable(get_provider_config)
        assert callable(get_role_configs)

    def test_role_registry_importable(self):
        """role_registry 模块应可导入"""
        from references.role_registry import scan, get_all_roles
        assert callable(scan)
        assert callable(get_all_roles)

    def test_tools_registry_importable(self):
        """tools_registry 模块应可导入"""
        from references.tools_registry import execute_tool, get_tools_for_role
        assert callable(execute_tool)
        assert callable(get_tools_for_role)

    def test_resource_library_importable(self):
        """resource_library 模块应可导入"""
        from references.resource_library import search, init_resource_library
        assert callable(search)
        assert callable(init_resource_library)
