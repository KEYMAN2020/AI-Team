"""启动脚本：清除代理后启动 server.py。
API Key 从系统环境变量读取（DEEPSEEK_API_KEY 等），无需 .env 文件。"""
import os
import sys

# 禁用代理（避免 httpx/OpenAI SDK 经过代理导致连接问题）
for _pv in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(_pv, None)

# 启动 server
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import main
main()
