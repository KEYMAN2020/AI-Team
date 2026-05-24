"""
test_docker.py — Docker 配置验证测试
"""
import os


class TestDockerConfig:
    """验证 Docker 相关配置文件"""

    def test_dockerfile_exists(self):
        assert os.path.exists("Dockerfile"), "Dockerfile 不存在"

    def test_dockerfile_has_healthcheck(self):
        with open("Dockerfile", encoding="utf-8") as f:
            content = f.read()
        assert "HEALTHCHECK" in content, "Dockerfile 缺少 HEALTHCHECK"
        assert "EXPOSE" in content, "Dockerfile 缺少 EXPOSE"

    def test_docker_compose_exists(self):
        assert os.path.exists("docker-compose.yml"), "docker-compose.yml 不存在"

    def test_docker_compose_has_healthcheck(self):
        with open("docker-compose.yml", encoding="utf-8") as f:
            content = f.read()
        assert "healthcheck" in content, "docker-compose.yml 缺少 healthcheck"

    def test_dockerignore_exists(self):
        assert os.path.exists(".dockerignore"), ".dockerignore 不存在"
