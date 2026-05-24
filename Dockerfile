# =============================================================================
# Dockerfile — AI-TeaM 多 Agent 协作平台
# =============================================================================
# 多阶段构建：第一阶段安装依赖，第二阶段运行
# 基础镜像：python:3.11-slim（平衡体积与兼容性）
# =============================================================================
# 构建：
#   docker build -t ai-team:latest .
# 运行：
#   docker run -d --env-file .env -p 8123:8123 ai-team:latest
# =============================================================================

# ---- Stage 1: 依赖安装 ----
FROM python:3.11-slim AS builder

LABEL maintainer="AI-TeaM DevOps"
LABEL description="AI-TeaM Multi-Agent Collaboration Platform"

# 设置 Python 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .

# 安装系统依赖（用于编译某些 Python 包）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: 运行镜像 ----
FROM python:3.11-slim

LABEL maintainer="AI-TeaM DevOps"
LABEL description="AI-TeaM Multi-Agent Collaboration Platform"
LABEL org.opencontainers.image.source="https://github.com/ai-team/server"
LABEL org.opencontainers.image.version="${AI_TEAM_VERSION:-latest}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_TEAM_HOST=0.0.0.0 \
    AI_TEAM_PORT=8123 \
    TZ=Asia/Shanghai

WORKDIR /app

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/bin/curl /usr/bin/curl

# 复制应用代码
COPY server.py .
COPY requirements.txt .
COPY ait .
COPY config/ ./config/
COPY references/ ./references/

# 创建运行时目录
RUN mkdir -p /app/state /app/outputs /app/logs /app/knowledge/curated /app/knowledge/auto

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:8123/health || exit 1

# 暴露端口
EXPOSE 8123

# 非 root 用户运行（安全）
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --gid 1000 appuser && \
    chown -R appuser:appgroup /app
USER appuser

# 启动命令
CMD ["python", "server.py"]
