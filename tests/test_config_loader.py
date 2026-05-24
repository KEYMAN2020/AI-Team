"""
test_config_loader.py — 配置加载器单元测试
"""
import os
import yaml
import pytest
from pathlib import Path


class TestConfigLoaderEnvExpansion:
    """环境变量展开测试"""

    def test_expand_env_simple(self, monkeypatch):
        """${VAR} 应被替换为环境变量值"""
        monkeypatch.setenv("MY_VAR", "hello")
        from references.config_loader import _expand_env
        result = _expand_env("prefix-${MY_VAR}-suffix")
        assert result == "prefix-hello-suffix"

    def test_expand_env_default(self, monkeypatch):
        """${VAR:-default} 应使用默认值"""
        from references.config_loader import _expand_env
        result = _expand_env("${UNDEFINED_VAR:-fallback}")
        assert result == "fallback"

    def test_expand_env_missing_no_default(self, monkeypatch):
        """${VAR} 不存在的变量应替换为空"""
        from references.config_loader import _expand_env
        result = _expand_env("x${NONEXISTENT_VAR_12345}y")
        assert result == "xy"

    def test_expand_env_dict(self, monkeypatch):
        """_expand_env 应递归展开 dict 中的值"""
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "5432")
        from references.config_loader import _expand_env
        data = {"db": {"host": "${HOST}", "port": "${PORT}"}}
        result = _expand_env(data)
        assert result["db"]["host"] == "localhost"
        assert result["db"]["port"] == "5432"

    def test_expand_env_list(self, monkeypatch):
        """_expand_env 应递归展开 list 中的值"""
        monkeypatch.setenv("BASE", "/app")
        from references.config_loader import _expand_env
        data = ["${BASE}/config", "${BASE}/data"]
        result = _expand_env(data)
        assert result == ["/app/config", "/app/data"]


class TestConfigLoaderYaml:
    """YAML 配置加载测试"""

    def test_load_yaml_empty_if_not_exists(self, monkeypatch):
        """YAML 文件不存在应返回空 dict"""
        from references.config_loader import _load_yaml
        # 清空缓存确保独立
        import references.config_loader as cl
        with cl._cache_lock:
            cl._cache.clear()
        result = _load_yaml("nonexistent_file.yaml")
        assert result == {}

    def test_get_provider_config(self):
        """get_provider_config() 应返回 providers.yaml 内容"""
        from references.config_loader import get_provider_config
        import references.config_loader as cl
        with cl._cache_lock:
            cl._cache.clear()
        cfg = get_provider_config()
        # 该文件存在于项目 config/ 中
        assert isinstance(cfg, dict)

    def test_get_active_provider_default(self):
        """get_active_provider() 应返回 valid provider"""
        from references.config_loader import get_active_provider
        provider = get_active_provider()
        assert provider in ("deepseek", "claude", "openai", "gemini", "any")

    def test_get_default_timeout(self):
        """get_default_timeout() 应返回 int"""
        from references.config_loader import get_default_timeout
        timeout = get_default_timeout()
        assert isinstance(timeout, int)
        assert timeout > 0

    def test_get_workflow_config(self):
        """get_workflow_config() 应返回 workflow config"""
        from references.config_loader import get_workflow_config
        import references.config_loader as cl
        with cl._cache_lock:
            cl._cache.clear()
        cfg = get_workflow_config()
        assert isinstance(cfg, dict)
        assert "default_timeout" in cfg
        assert "default_retries" in cfg

    def test_get_workflow_value(self):
        """get_workflow_value() 应返回指定 key 的值"""
        from references.config_loader import get_workflow_value
        import references.config_loader as cl
        with cl._cache_lock:
            cl._cache.clear()
        timeout = get_workflow_value("default_timeout")
        assert isinstance(timeout, int)


class TestConfigLoaderCaching:
    """配置缓存测试"""

    def test_cache_hits(self, monkeypatch):
        """反复调用应命中缓存"""
        import references.config_loader as cl
        with cl._cache_lock:
            cl._cache.clear()

        from references.config_loader import get_provider_config
        # 第一次调用 - 读文件
        cfg1 = get_provider_config()
        # 第二次调用 - 应走缓存
        cfg2 = get_provider_config()
        assert cfg1 == cfg2
