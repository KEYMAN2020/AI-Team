#!/bin/bash
# =============================================================================
# rollback.sh — stopBtn 回滚脚本
# =============================================================================
# 用法：
#   bash scripts/rollback.sh                    # 回滚到上一个版本
#   bash scripts/rollback.sh v1.0.0             # 回滚到指定版本
#   bash scripts/rollback.sh staging v1.0.0     # 回滚 Staging 到指定版本
# =============================================================================

set -euo pipefail

# ── 颜色输出 ──────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 参数解析 ──────────────────────────────────────────
ENVIRONMENT="${1:-production}"
TARGET_VERSION="${2:-}"

# 如果第一个参数是版本号（以 v 开头），则环境默认为 production
if [[ "$ENVIRONMENT" =~ ^v ]]; then
    TARGET_VERSION="$ENVIRONMENT"
    ENVIRONMENT="production"
fi

# 验证环境参数
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    log_error "环境参数必须是 staging 或 production"
    echo "用法: bash scripts/rollback.sh [staging|production] [version]"
    exit 1
fi

# ── 配置 ──────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── 获取当前版本 ──────────────────────────────────────
CURRENT_VERSION=$(docker inspect --format '{{index .Config.Labels "com.stopbtn.version"}}' \
    stopbtn-backend 2>/dev/null || echo "unknown")

log_info "当前版本: ${CURRENT_VERSION}"

# ── 确定目标版本 ──────────────────────────────────────
if [ -z "$TARGET_VERSION" ]; then
    # 没有指定版本，尝试获取上一个版本
    log_info "未指定目标版本，尝试获取上一个版本..."
    
    # 从 Docker 镜像列表中获取上一个版本
    PREVIOUS_VERSION=$(docker images --format '{{.Tag}}' \
        --filter=reference='stopbtn-backend' \
        | grep -v "$CURRENT_VERSION" \
        | sort -V \
        | tail -1 2>/dev/null || echo "")
    
    if [ -z "$PREVIOUS_VERSION" ]; then
        log_error "无法自动确定上一个版本"
        log_info "请指定目标版本: bash scripts/rollback.sh ${ENVIRONMENT} v1.0.0"
        exit 1
    fi
    
    TARGET_VERSION="$PREVIOUS_VERSION"
fi

log_info "目标版本: ${TARGET_VERSION}"

# ── 确认回滚 ──────────────────────────────────────────
echo ""
log_warn "══════════════════════════════════════════════════════════════"
log_warn "  即将执行回滚操作"
log_warn "  环境: ${ENVIRONMENT}"
log_warn "  当前版本: ${CURRENT_VERSION}"
log_warn "  目标版本: ${TARGET_VERSION}"
log_warn "══════════════════════════════════════════════════════════════"
echo ""

read -p "确认回滚? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    log_info "回滚已取消"
    exit 0
fi

# ── 执行回滚 ──────────────────────────────────────────
log_info "步骤 1/3: 停止当前服务"
if [ "$ENVIRONMENT" == "production" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down
else
    docker compose -f docker-compose.yml down
fi
log_ok "服务已停止"

log_info "步骤 2/3: 回滚到版本 ${TARGET_VERSION}"
export STOPBTN_VERSION="$TARGET_VERSION"

if [ "$ENVIRONMENT" == "production" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
else
    docker compose -f docker-compose.yml up -d
fi
log_ok "服务已启动"

log_info "步骤 3/3: 等待健康检查"
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

# ── 回滚完成 ──────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  回滚完成！${NC}"
echo -e "${GREEN}  环境: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}  当前版本: ${TARGET_VERSION}${NC}"
echo -e "${GREEN}  后端: http://localhost:${BACKEND_PORT:-8000}${NC}"
echo -e "${GREEN}  前端: http://localhost:${FRONTEND_PORT:-3000}${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# ── 记录回滚日志 ──────────────────────────────────────
ROLLBACK_LOG="rollback_history.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rollback: ${ENVIRONMENT} from ${CURRENT_VERSION} to ${TARGET_VERSION}" >> "$ROLLBACK_LOG"
log_info "回滚日志已记录到 ${ROLLBACK_LOG}"