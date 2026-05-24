#!/bin/bash
# =============================================================================
# deploy.sh — stopBtn 部署脚本
# =============================================================================
# 用法：
#   bash scripts/deploy.sh staging          # 部署到 Staging
#   bash scripts/deploy.sh production       # 部署到 Production
#   bash scripts/deploy.sh production v1.2.3  # 部署指定版本
# =============================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 参数解析 ──────────────────────────────────────────
ENVIRONMENT="${1:-staging}"
VERSION="${2:-latest}"

# 验证环境参数
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    log_error "环境参数必须是 staging 或 production"
    echo "用法: bash scripts/deploy.sh [staging|production] [version]"
    exit 1
fi

# ── 配置 ──────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 设置默认值
export STOPBTN_VERSION="${VERSION:-latest}"
export APP_ENV="$ENVIRONMENT"

# ── 前置检查 ──────────────────────────────────────────
log_info "开始部署到 ${ENVIRONMENT} 环境 (版本: ${STOPBTN_VERSION})"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    log_error "Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查 docker-compose 是否可用
if ! docker compose version > /dev/null 2>&1; then
    log_error "docker compose 不可用"
    exit 1
fi

# ── 部署流程 ──────────────────────────────────────────
log_info "步骤 1/4: 拉取最新镜像"
if [ "$ENVIRONMENT" == "production" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
else
    docker compose -f docker-compose.yml build
fi
log_ok "镜像准备完成"

log_info "步骤 2/4: 启动服务"
if [ "$ENVIRONMENT" == "production" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
else
    docker compose -f docker-compose.yml up -d
fi
log_ok "服务已启动"

log_info "步骤 3/4: 等待健康检查"
# 等待后端健康检查
BACKEND_HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:${BACKEND_PORT:-8000}/health > /dev/null 2>&1; then
        BACKEND_HEALTHY=true
        log_ok "后端服务健康检查通过"
        break
    fi
    sleep 2
done

if [ "$BACKEND_HEALTHY" = false ]; then
    log_error "后端服务健康检查超时"
    log_info "查看日志: docker compose logs backend"
    exit 1
fi

# 等待前端健康检查
FRONTEND_HEALTHY=false
for i in $(seq 1 15); do
    if curl -sf http://localhost:${FRONTEND_PORT:-3000}/health > /dev/null 2>&1; then
        FRONTEND_HEALTHY=true
        log_ok "前端服务健康检查通过"
        break
    fi
    sleep 2
done

if [ "$FRONTEND_HEALTHY" = false ]; then
    log_warn "前端服务健康检查超时，请手动检查"
fi

log_info "步骤 4/4: 清理旧镜像"
docker image prune -f --filter "until=24h" 2>/dev/null || true
log_ok "旧镜像清理完成"

# ── 部署完成 ──────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}  环境: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}  版本: ${STOPBTN_VERSION}${NC}"
echo -e "${GREEN}  后端: http://localhost:${BACKEND_PORT:-8000}${NC}"
echo -e "${GREEN}  前端: http://localhost:${FRONTEND_PORT:-3000}${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
log_info "查看日志: docker compose logs -f"
log_info "停止服务: docker compose down"