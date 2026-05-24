"""
test_config.py — 配置文件完整性测试
"""
import os
import yaml


class TestConfigFiles:
    """验证所有 YAML 配置文件格式正确"""

    CONFIG_DIR = "config"

    def test_providers_yaml(self):
        path = os.path.join(self.CONFIG_DIR, "providers.yaml")
        assert os.path.exists(path), f"{path} 不存在"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "active_provider" in data
        assert data["active_provider"] in ("deepseek", "claude", "openai", "gemini", "any")

    def test_roles_yaml(self):
        path = os.path.join(self.CONFIG_DIR, "roles.yaml")
        assert os.path.exists(path), f"{path} 不存在"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "deepseek" in data or "claude" in data or "openai" in data

    def test_workflow_yaml(self):
        path = os.path.join(self.CONFIG_DIR, "workflow.yaml")
        assert os.path.exists(path), f"{path} 不存在"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "default_timeout" in data
        assert "default_retries" in data
