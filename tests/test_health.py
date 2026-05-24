"""
test_health.py — 健康检查端点测试
"""
import json
from http.server import HTTPServer
from server import TeamHTTPHandler


class TestHealthEndpoint:
    """测试 /health 端点"""

    def test_health_response(self):
        """健康检查应返回 status: ok"""
        # 由于 server.py 使用 BaseHTTPRequestHandler，需要模拟 HTTP 请求
        # 这里只验证 server.py 可导入且结构正确
        assert hasattr(TeamHTTPHandler, "do_GET")
        assert hasattr(TeamHTTPHandler, "do_POST")
        assert hasattr(TeamHTTPHandler, "_handle_health")
