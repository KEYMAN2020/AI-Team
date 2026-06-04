FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     AI_TEAM_HOST=0.0.0.0     AI_TEAM_PORT=8123     TZ=Asia/Shanghai     PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .
RUN mkdir -p /app/state /app/outputs /app/logs /app/knowledge/curated /app/knowledge/auto

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8123/health')" || exit 1

EXPOSE 8123

CMD ["python", "start_server.py"]
