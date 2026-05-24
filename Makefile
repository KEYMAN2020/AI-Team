# =============================================================================
# Makefile — AI-TeaM 开发/部署常用命令
# =============================================================================
# 用法：
#   make help          # 显示帮助
#   make install       # 安装依赖
#   make dev           # 本地开发启动
#   make test          # 运行测试
#   make lint          # 代码检查
#   make build         # 构建 Docker 镜像
#   make up            # 启动所有服务
#   make down          # 停止所有服务
#   make logs          # 查看日志
#   make restart       # 重启服务
#   make clean         # 清理缓存
# =============================================================================

.PHONY: help install dev test lint build up down logs restart clean

# ── 变量 ──────────────────────────────────────────────
DOCKER_COMPOSE := docker compose
DOCKER_COMPOSE_FILES := -f docker-compose.yml
DOCKER_COMPOSE_PROD_FILES := -f docker-compose.yml -f docker-compose.prod.yml
PYTHON := python3
PIP := pip3

# ── 帮助 ──────────────────────────────────────────────
help: ## 显示帮助信息
	@echo "AI-TeaM 开发/部署命令"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── 本地开发 ──────────────────────────────────────────
install: ## 安装 Python 依赖
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-asyncio flake8 black isort mypy bandit safety

dev: ## 本地开发启动（热重载）
	$(PYTHON) server.py

test: ## 运行测试
	$(PYTHON) -m pytest tests/ -v --cov=. --cov-report=term --cov-report=html

lint: ## 代码质量检查
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	black --check --diff . || echo "⚠ 请运行: black ."
	isort --check-only --diff . || echo "⚠ 请运行: isort ."

format: ## 自动格式化代码
	black .
	isort .

security: ## 安全扫描
	bandit -r . -f json -o bandit-report.json || true
	safety check -r requirements.txt --full-report || true

# ── Docker ────────────────────────────────────────────
build: ## 构建 Docker 镜像
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) build

build-prod: ## 构建生产镜像（使用预构建）
	docker build -t ai-team:latest .

up: ## 启动所有服务（开发模式）
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) up -d

up-prod: ## 启动所有服务（生产模式）
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_PROD_FILES) up -d

down: ## 停止所有服务
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) down

down-prod: ## 停止生产环境服务
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_PROD_FILES) down

restart: ## 重启所有服务
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) restart

restart-prod: ## 重启生产环境服务
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_PROD_FILES) restart

logs: ## 查看日志
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) logs -f

logs-prod: ## 查看生产环境日志
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_PROD_FILES) logs -f

ps: ## 查看服务状态
	$(DOCKER_COMPOSE) $(DOCKER_COMPOSE_FILES) ps

# ── 部署 ──────────────────────────────────────────────
deploy-staging: ## 部署到 Staging
	bash scripts/deploy.sh staging

deploy-production: ## 部署到 Production
	bash scripts/deploy.sh production

rollback: ## 回滚到上一个版本
	bash scripts/rollback.sh

# ── 清理 ──────────────────────────────────────────────
clean: ## 清理缓存和临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .coverage coverage.xml test-results.xml
	rm -rf bandit-report.json htmlcov/
	rm -rf .tox/
	@echo "✅ 清理完成"

clean-docker: ## 清理 Docker 资源
	docker system prune -f --volumes 2>/dev/null || true
	@echo "✅ Docker 清理完成"