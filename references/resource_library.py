"""
resource_library.py — 技术知识储备库
=======================================
与 knowledge_base.py 的区别：
  knowledge_base  →  项目专属（本项目的决策、规范、踩坑）
  resource_library →  通用技术知识（设计模式、最佳实践、安全检查单）
                      跨项目共享，项目启动时自动加载，不随项目重置

目录：resource_library/
  frontend/      前端最佳实践、组件模式、性能优化
  backend/       后端模式、API设计、性能、中间件
  database/      数据库设计、索引优化、事务、迁移
  security/      安全检查单、常见漏洞、加密规范
  testing/       测试策略、测试模式、Mock方法
  architecture/  架构模式、设计原则、系统设计
  devops/        部署模式、容器化、CI/CD

每个角色查询时，resource_library 返回最相关的片段（关键词匹配）。
"""

import re
from pathlib import Path
from typing import Optional

LIB_DIR = Path("resource_library")

CATEGORY_MAP = {
    # ══ 硬编码 fallback（role_registry 不可用时使用） ══
    "pm":        ["architecture"],
    "product":   [],
    "architect": ["architecture", "backend", "database", "security"],
    "ux":        ["frontend"],
    "dba":       ["database"],
    "frontend":  ["frontend", "testing", "security"],
    "backend":   ["backend", "database", "security", "testing"],
    "reviewer":  ["security", "backend", "frontend", "testing"],
    "devops":    ["devops", "security"],
    "debug":     ["backend", "frontend", "database"],
    "tester":    ["testing"],
}

# ── 从 role_registry 覆盖资源分类（优先） ──
try:
    from role_registry import get_role_resource_cats as _get_role_resource_cats, get_all_roles as _get_all_roles
    for _role in _get_all_roles():
        _reg_cats = _get_role_resource_cats(_role)
        if _reg_cats:
            CATEGORY_MAP[_role] = _reg_cats
    del _get_role_resource_cats, _get_all_roles  # 清理模块级变量
except ImportError:
    pass


# ── 初始化（预加载通用知识）────────────────────────

def init_resource_library() -> None:
    """初始化知识储备库，写入预置的通用技术知识。"""
    LIB_DIR.mkdir(exist_ok=True)
    for cat in CATEGORY_MAP.values():
        for c in cat:
            (LIB_DIR / c).mkdir(exist_ok=True)

    _write_if_not_exists("architecture/design_principles.md",     _ARCHITECTURE)
    _write_if_not_exists("backend/api_design.md",                 _BACKEND_API)
    _write_if_not_exists("backend/error_handling.md",             _BACKEND_ERRORS)
    _write_if_not_exists("database/schema_patterns.md",           _DB_PATTERNS)
    _write_if_not_exists("security/checklist.md",                 _SECURITY)
    _write_if_not_exists("frontend/component_patterns.md",        _FRONTEND)
    _write_if_not_exists("testing/strategies.md",                 _TESTING)
    _write_if_not_exists("devops/deployment_patterns.md",         _DEVOPS)

    print(f"✅ 知识储备库已就绪：{LIB_DIR}/")


def _write_if_not_exists(rel_path: str, content: str) -> None:
    path = LIB_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


# ── 查询接口 ─────────────────────────────────────

def search(query: str, top_k: int = 3,
           categories: Optional[list] = None) -> str:
    """
    关键词搜索知识库，返回最相关的片段。
    agents 在不确定某个技术决策时调用。
    """
    keywords = re.findall(r'\w+', query.lower())
    results = []

    search_dirs = []
    if categories:
        search_dirs = [LIB_DIR / c for c in categories if (LIB_DIR / c).exists()]
    else:
        search_dirs = [d for d in LIB_DIR.iterdir() if d.is_dir()]

    for cat_dir in search_dirs:
        for fp in cat_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            # 计算关键词命中分
            score = sum(text.lower().count(kw) for kw in keywords)
            if score > 0:
                # 提取最相关的段落
                paragraphs = text.split("\n\n")
                best_para = max(paragraphs,
                                key=lambda p: sum(p.lower().count(kw) for kw in keywords),
                                default="")
                if best_para.strip():
                    results.append((score, f"[{cat_dir.name}/{fp.stem}]\n{best_para.strip()[:600]}"))

    results.sort(key=lambda x: x[0], reverse=True)
    if not results:
        return f"知识库中未找到与「{query}」相关的内容。"

    return "\n\n---\n\n".join(r[1] for r in results[:top_k])


def get_category(category: str) -> str:
    """获取某个分类的全部知识。"""
    cat_dir = LIB_DIR / category
    if not cat_dir.exists():
        return f"分类「{category}」不存在。"
    files = list(cat_dir.glob("*.md"))
    if not files:
        return f"分类「{category}」暂无内容。"
    parts = []
    for fp in sorted(files):
        content = fp.read_text(encoding="utf-8")
        parts.append(f"### {fp.stem}\n{content[:1000]}")
    return "\n\n".join(parts)


def build_library_context(role: str, task: str = "") -> str:
    """
    为角色构建知识库上下文注入内容。
    如果有具体任务描述，做关键词搜索；否则返回角色相关分类的摘要。
    自动解析别名。
    """
    try:
        from role_registry import resolve_role as _resolve
        role = _resolve(role) or role
    except ImportError:
        pass
    categories = CATEGORY_MAP.get(role, [])
    if not categories:
        return ""

    if task:
        result = search(task, top_k=2, categories=categories)
        if "未找到" not in result:
            return f"[技术知识库参考]\n{result}"
        return ""

    # 无任务时返回分类摘要（简短）
    parts = []
    for cat in categories[:2]:
        snippet = get_category(cat)
        if snippet and "暂无" not in snippet:
            parts.append(f"[{cat}] " + snippet[:300])
    return "\n".join(parts) if parts else ""


def save_to_library(category: str, title: str, content: str) -> None:
    """将新知识保存到库中（跨项目复用）。"""
    path = LIB_DIR / category / f"{title.replace(' ', '_')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{content}", encoding="utf-8")
    print(f"✅ 已保存到知识库：{path}")


# ══════════════════════════════════════════════════
# 预置知识内容
# ══════════════════════════════════════════════════

_ARCHITECTURE = """# 架构设计原则

## SOLID 原则
- **S** 单一职责：每个模块只做一件事
- **O** 开闭原则：对扩展开放，对修改关闭
- **L** 里氏替换：子类可替换父类
- **I** 接口隔离：细粒度接口优于大而全
- **D** 依赖倒置：依赖抽象而非具体实现

## 常用架构模式
- **分层架构**：Controller → Service → Repository → DB（清晰边界，易于测试）
- **CQRS**：读写分离，Command 写数据，Query 读数据（高并发场景）
- **事件驱动**：通过事件解耦组件（适合异步处理、审计日志）
- **微服务**：按业务域拆分服务（适合团队独立发布需求）

## API 设计原则
- REST: 资源导向，使用 HTTP 动词（GET/POST/PUT/PATCH/DELETE）
- 版本化：URL 前缀 /api/v1 或 Header Accept-Version
- 分页：cursor-based 优于 offset（大数据量时性能更好）
- 幂等性：PUT/DELETE 必须幂等；POST 通过 idempotency-key 实现

## 系统设计要点
- 单点故障（SPOF）：识别并消除关键路径上的单点
- 水平扩展：无状态设计，Session 存 Redis
- 缓存策略：Cache-Aside / Write-Through / Write-Behind 按场景选择
- 限流熔断：令牌桶/漏桶限流，Circuit Breaker 防雪崩
"""

_BACKEND_API = """# 后端 API 设计规范

## 统一响应格式
```json
{
  "code": 0,
  "msg": "ok",
  "data": {},
  "request_id": "uuid"
}
```
错误时 code 为非零，msg 为用户友好错误描述，data 可附错误详情。

## 错误码设计
- 1xxxx：业务错误（如 10001 用户不存在）
- 2xxxx：权限错误（如 20001 未登录）
- 3xxxx：参数错误（如 30001 参数缺失）
- 5xxxx：系统错误（如 50001 数据库异常）

## RESTful 命名规范
- 资源复数：/users, /orders, /products
- 嵌套资源：/users/{id}/orders（不超过两层）
- 动作用动词前缀：POST /users/{id}/activate（非 CRUD 操作）

## 参数校验
- 必须在 Controller 层做完整校验，不能让非法参数进入 Service
- 使用 Pydantic (Python) / Zod (TS) / Jakarta Validation (Java)
- 校验失败统一返回 400，body 包含具体字段错误

## 分页规范
```json
{"data": [], "total": 100, "page": 1, "page_size": 20, "has_more": true}
```

## 幂等性
- POST 创建资源：客户端传 idempotency_key，服务端 Redis 去重
- 支付、发券等高风险操作必须实现幂等
"""

_BACKEND_ERRORS = """# 错误处理最佳实践

## 错误分层
- **已知业务错误**：抛自定义异常（BusinessException），包含错误码和描述
- **参数错误**：校验框架自动处理，统一 400 响应
- **系统错误**：捕获后记录完整堆栈，返回 500，不暴露内部细节

## 日志规范
```python
# 正确：结构化日志
logger.error("order_failed", order_id=order_id, user_id=user_id, error=str(e))
# 错误：字符串拼接，无法过滤
logger.error(f"error: {e}")
```

## 禁止事项
- 禁止空 except/catch（掩盖错误）
- 禁止在日志中打印密码、token、信用卡号
- 禁止直接将异常信息返回给前端（暴露内部实现）
- 禁止使用 print 替代日志（生产环境无法采集）

## 重试策略
- 网络超时、数据库临时不可用：指数退避重试，最多3次
- 业务逻辑错误（如余额不足）：不重试
- 使用 tenacity (Python) / retry (Go) 等库，不要手写循环
"""

_DB_PATTERNS = """# 数据库设计模式

## 表设计规范
- 必备字段：id (BIGSERIAL PK), created_at, updated_at（用 trigger 自动更新）
- 软删除：is_deleted BOOLEAN DEFAULT FALSE + deleted_at（审计需要）
- 外键约束：显式声明 FOREIGN KEY，不要只靠代码保证
- 命名：表名复数 snake_case，字段 snake_case，外键 {table}_id

## 索引策略
- 主键自带索引，无需重复创建
- 高频 WHERE 字段加索引：状态字段、外键字段、时间范围查询字段
- 联合索引：最左前缀原则，把区分度高的字段放左边
- 避免在低区分度字段建索引（如 gender, is_active）
- EXPLAIN ANALYZE 验证索引是否被使用

## 常见性能陷阱
- N+1 查询：ORM 关联查询必须用 JOIN 或 prefetch_related
- 全表扫描：WHERE 子句确保命中索引
- 大事务：事务尽量小，避免长时间锁表
- SELECT *：只查需要的字段，大表尤其注意

## Migration 规范
- 每次变更一个独立 migration 文件，包含 up 和 down
- 生产环境先在测试环境验证
- 添加列：可热更新；删除列：先废弃再删除（两步发布）
- 大表加索引：使用 CONCURRENTLY 避免锁表

## 事务使用
- 跨表操作必须用事务
- 事务边界在 Service 层，不在 Repository 层
- 读操作不需要事务（除非需要一致性读）
"""

_SECURITY = """# 安全开发检查单

## 输入验证（必须）
- [ ] 所有用户输入经过服务端校验（不信任前端校验）
- [ ] SQL 查询使用参数化，禁止字符串拼接
- [ ] 文件上传：校验类型、大小、重命名存储
- [ ] 正则匹配：防止 ReDoS（避免嵌套量词）

## 认证与授权（必须）
- [ ] 密码使用 bcrypt/argon2 哈希，不存明文
- [ ] JWT secret 足够随机（至少 256 位），不硬编码
- [ ] 敏感操作（改密码、删除）需要重新验证身份
- [ ] 接口做最小权限控制（用户只能操作自己的资源）

## 数据安全（必须）
- [ ] 敏感字段加密存储（身份证、手机号、银行卡）
- [ ] 日志脱敏（手机号 130****1234，密码不记录）
- [ ] HTTPS 全站，敏感接口禁止降级到 HTTP

## 常见漏洞防护
- XSS：前端输出做 HTML 转义；设置 Content-Security-Policy
- CSRF：API 使用 Token 认证（不用 Cookie）；或加 CSRF Token
- 越权：接口必须校验资源归属
- 信息泄露：错误响应不暴露堆栈和系统信息
- 依赖漏洞：定期 npm audit / pip-audit

## 配置安全
- [ ] 密钥通过环境变量或 Secret Manager 注入，不进代码库
- [ ] 生产环境 DEBUG 模式关闭
- [ ] 数据库账号最小权限（应用账号不用 root）
"""

_FRONTEND = """# 前端开发最佳实践

## 组件设计原则
- 单一职责：一个组件只做一件事
- 受控/非受控：状态提升到最近的公共父组件
- 组合优于继承：用 children/slot 实现复用
- Props 向下，Events 向上（单向数据流）

## 状态管理
- 本地 UI 状态：useState（不需要共享的状态）
- 跨组件状态：Context / Zustand（轻量）/ Redux（复杂场景）
- 服务端状态：React Query / SWR（自动缓存、重试、同步）

## 性能优化
- 大列表：虚拟滚动（react-virtual / vue-virtual-scroller）
- 重渲染：React.memo / useMemo / useCallback（先 profile 再优化）
- 代码分割：路由级别懒加载（React.lazy + Suspense）
- 图片：WebP 格式，懒加载，合适尺寸

## 错误处理
- API 调用：统一错误拦截（axios interceptor），用户友好提示
- 边界情况：ErrorBoundary 捕获渲染错误
- Loading/Empty/Error 三态：每个数据依赖区域都要处理

## 可访问性（a11y）
- 语义化 HTML：button 做按钮，a 做链接
- 图片必须有 alt 属性
- 表单 label 关联 input（for/id）
- 键盘可操作：所有交互元素可 Tab 到达
- 颜色对比度：正文 ≥ 4.5:1（WCAG AA 标准）
"""

_TESTING = """# 测试策略指南

## 测试金字塔
- 单元测试（70%）：快速、隔离、大量
- 集成测试（20%）：测试模块间交互
- E2E 测试（10%）：测试关键用户路径

## 单元测试原则（FIRST）
- Fast：测试应该在毫秒级完成
- Independent：测试互不依赖，可任意顺序执行
- Repeatable：任何环境下结果一致（mock 外部依赖）
- Self-validating：明确的 pass/fail，不需要人工判断
- Timely：与代码同步编写（TDD 或同步写）

## Mock 使用规范
- Mock 外部依赖（数据库、第三方 API、文件系统）
- 不 Mock 被测逻辑本身
- 使用工厂函数创建测试数据，不硬编码大量字段

## 测试命名规范
```
test_[被测函数]_[场景]_[预期结果]
例：test_create_user_with_duplicate_email_raises_conflict
```

## 覆盖率目标
- 核心业务逻辑：≥ 80%
- 工具函数：≥ 90%
- 覆盖率是指标，不是目标——重要的是测试有意义

## 回归测试
- 每个 Bug 修复必须附一个能暴露该 Bug 的测试用例
- 测试用例在 PR 合并前必须通过
"""

_DEVOPS = """# DevOps 与部署最佳实践

## 容器化规范
- 使用官方基础镜像（alpine 变体，减小攻击面）
- 多阶段构建（builder + runtime 分离）
- 非 root 用户运行进程
- .dockerignore 排除 node_modules、.env、.git

## 环境变量管理
- 开发：.env 文件（不进代码库，用 .env.example 做模板）
- 生产：Secret Manager（AWS Secrets Manager / Vault / K8s Secret）
- 不同环境用不同配置，代码不做环境判断

## CI/CD 流水线阶段
1. Lint + 格式检查
2. 单元测试
3. 构建（Docker image）
4. 集成测试
5. 安全扫描（依赖漏洞、镜像扫描）
6. 部署到 Staging
7. E2E 测试
8. 人工确认 → 部署到生产

## 部署策略
- 蓝绿部署：零停机，快速回滚（维护两套环境）
- 滚动更新：逐步替换，节省资源
- 金丝雀发布：先给 5% 流量，观察后全量

## 健康检查
- Liveness probe：进程是否存活（失败则重启容器）
- Readiness probe：是否准备好接流量（失败则从负载均衡摘除）
- Startup probe：慢启动应用的初始化等待

## 日志与监控
- 结构化日志输出到 stdout（容器化标准）
- 关键指标：错误率、P50/P99 延迟、QPS、饱和度
- 告警阈值：错误率 > 1%、P99 > 2s、磁盘 > 80%
"""
