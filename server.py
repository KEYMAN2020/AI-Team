# AI-TeaM HTTP Server
# ====================
# Cherry Studio（人类 I/O）→ n8n（工作流编排）→ server.py → LLM API（多 Agent 执行）
#
# 端點：
#   POST /run         提交项目任务，返回 task_id（异步执行）
#   GET  /status      查看当前项目和所有角色状态
#   GET  /health      健康检查
#   POST /approve     批准等待中的人工审批节点
#
# 用法：
#   python start_server.py   # 推荐（自动清除代理，keys 来自环境变量）
#   python server.py         # 直接启动（需先设好环境变量）
#
# ====================

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from queue import Queue, Empty

# ── 事件总线（SSE 实时推送） ──
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "references"))
import event_bus

# ── 清除代理（避免 httpx/OpenAI SDK 走代理导致连接问题）──
# API Key 通过系统环境变量注入，参见 .env.example
for _proxy_var in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(_proxy_var, None)

def _set_utf8_stdio():
    """Force UTF-8 on Windows stdout/stderr to avoid GBK encoding errors with emoji."""
    if sys.platform == "win32":
        import io
        for _s in (sys.stdout, sys.stderr):
            if hasattr(_s, "buffer"):
                try:
                    _replacement = io.TextIOWrapper(_s.buffer, encoding="utf-8", errors="replace")
                    if _s is sys.stdout:
                        sys.stdout = _replacement
                    else:
                        sys.stderr = _replacement
                except (ValueError, OSError):
                    pass

_set_utf8_stdio()

# Safe print – prevents "I/O operation on closed file" crash when asyncio
# closes stdout/stderr on Windows (ProactorEventLoop issue)
import builtins as _builtins
_original_print = _builtins.print
def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except (ValueError, OSError, UnicodeEncodeError):
        # UnicodeEncodeError: 子线程 stdout 可能是 GBK，emoji 编码失败时静默跳过
        pass
_builtins.print = _safe_print

# 将 references/ 加入 path，使各模块可直接导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "references"))

# ── 任务管理 ──────────────────────────────────────────
# 内存中的任务状态存储（n8n 轮询用）
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
# 并发保护：标记当前是否有项目正在执行，防止两个 /run 请求冲突
_project_running = False
_project_lock = threading.Lock()


def _get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        return _tasks.get(task_id)


def _set_task(task_id: str, data: dict) -> None:
    with _tasks_lock:
        _tasks[task_id] = data


# ═══════════════════════════════════════════════════════
# HTTP Handler
# ═══════════════════════════════════════════════════════

class TeamHTTPHandler(BaseHTTPRequestHandler):
    """为 n8n 提供 HTTP API 的请求处理器。"""

    def do_OPTIONS(self):
        self._send_cors(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/health":
            self._handle_health()
        elif path == "/status":
            self._handle_status()
        elif path.startswith("/status/"):
            task_id = path.split("/")[-1]
            self._handle_task_status(task_id)
        elif path == "/events":
            self._handle_sse()
        elif path in ("/dashboard", ""):
            self._handle_dashboard()
        elif path == "/api/state":
            self._handle_api_state()
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/run":
            self._handle_run()
        elif path == "/approve":
            self._handle_approve()
        elif path == "/approve-dag":
            self._handle_approve_dag()
        else:
            self._send_json(404, {"error": "Not Found"})

    # ── Handlers ─────────────────────────────────────

    def _handle_health(self):
        self._send_json(200, {
            "status": "ok",
            "version": "2.0",
            "timestamp": datetime.now().isoformat(),
        })

    def _handle_status(self):
        """返回当前项目的完整状态（从 master.json 读取）。"""
        try:
            from state_manager import get_project, list_checkpoints
            proj = get_project()
            cps = list_checkpoints()
            self._send_json(200, {
                "project": proj,
                "checkpoints": len(cps),
                "active_tasks": list(_tasks.keys()),
            })
        except FileNotFoundError:
            self._send_json(200, {
                "project": None,
                "message": "未初始化项目，请先 POST /run 提交任务",
            })

    def _handle_task_status(self, task_id: str):
        """查询某个异步任务的执行状态。"""
        task = _get_task(task_id)
        if not task:
            self._send_json(404, {"error": f"Task {task_id} not found"})
            return

        # 如果任务已完成，顺便从 state 读取最新项目信息
        result = dict(task)
        if task.get("status") in ("done", "partial"):
            try:
                from state_manager import get_project
                result["project"] = get_project()
            except Exception:
                pass

        self._send_json(200, result)

    def _handle_sse(self):
        """SSE 端点—推送实时事件给前端看板。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q, replay = event_bus.subscribe()
        try:
            # 先重放历史事件（让新页面看到已发生的进度）
            for raw in replay:
                sse_text = event_bus.format_sse(raw)
                try:
                    self.wfile.write(sse_text.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    return

            # 持续推送新事件
            while True:
                try:
                    raw = q.get(timeout=15)  # 15s 超时用于发心跳
                    sse_text = event_bus.format_sse(raw)
                    self.wfile.write(sse_text.encode("utf-8"))
                    self.wfile.flush()
                except Empty:
                    # 心跳 keepalive
                    try:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                    except Exception:
                        return
        finally:
            event_bus.unsubscribe(q)

    def _handle_dashboard(self):
        """提供实时看板 HTML。"""
        html_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "web_dashboard", "live_dashboard.html"
        )
        if not os.path.exists(html_path):
            self._send_json(404, {"error": "Dashboard HTML not found"})
            return
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_api_state(self):
        """JSON 接口—轮询兜底用（返回 master.json 快照）。"""
        try:
            from state_manager import get_project, list_checkpoints
            proj = get_project()
            cps = list_checkpoints()
            self._send_json(200, {
                "project": proj,
                "checkpoints": len(cps),
                "active_tasks": list(_tasks.keys()),
            })
        except FileNotFoundError:
            self._send_json(200, {"project": None, "message": "无活动项目"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_run(self):
        """提交一个项目开发任务，异步执行。

        请求体（JSON）：
          {
            "task": "实现用户注册登录功能，含 JWT 认证",
            "provider": "claude",          // 可选，默认用 ACTIVE_PROVIDER
            "project_name": "用户模块",      // 可选
            "webhook_url": "https://..."    // 可选，n8n 回调地址
          }

        返回：
          { "task_id": "proj_20260510_1430", "status": "running" }
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "无效的 JSON"})
            return

        task_desc = data.get("task", "").strip()
        if not task_desc:
            self._send_json(400, {"error": "缺少 task 字段"})
            return

        provider = data.get("provider")
        project_name = data.get("project_name", f"n8n_{datetime.now().strftime('%m%d_%H%M')}")
        webhook_url = data.get("webhook_url")

        # 在后台线程中执行
        task_id = f"task_{int(time.time())}"
        _set_task(task_id, {
            "task_id": task_id,
            "status": "running",
            "task": task_desc,
            "project_name": project_name,
            "started_at": datetime.now().isoformat(),
            "provider": provider,
            "webhook_url": webhook_url,
        })

        thread = threading.Thread(
            target=_run_async_task,
            args=(task_id, task_desc, project_name, provider, webhook_url),
            daemon=True,
        )
        thread.start()

        self._send_json(202, {
            "task_id": task_id,
            "status": "running",
            "message": "任务已提交，请轮询 GET /status/{task_id} 获取结果",
        })

    def _handle_approve(self):
        """批准等待中的人工审批节点（两阶段流程）。

        阶段一 — 开始审查（确认已看到）：
          {"status": "reviewing", "notes": "我开始审了"}

        阶段二 — 做出决定：
          {"approved": true, "notes": "方案没问题"}
          {"approved": false, "notes": "方案不合适"}
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "无效的 JSON"})
            return

        # 阶段一：用户确认已看到，开始审查
        if data.get("status") == "reviewing":
            ack_file = os.path.join(PROJECT_ROOT, "state", "_approval_ack.json")
            os.makedirs(os.path.dirname(ack_file), exist_ok=True)
            with open(ack_file, "w", encoding="utf-8") as f:
                json.dump({
                    "acknowledged": True,
                    "notes": data.get("notes", ""),
                    "timestamp": datetime.now().isoformat(),
                }, f)
            self._send_json(200, {"status": "reviewing", "message": "已确认，计时开始"})
            return

        # 阶段二：用户做出决定
        approved = data.get("approved")
        if approved is None:
            self._send_json(400, {"error": "请指定 approved: true/false 或 status: 'reviewing'"})
            return

        notes = data.get("notes", "通过 HTTP API 批准")

        # 将审批结果写入一个临时文件，runner.py 的 _request_human_approval 会读取
        approval_file = os.path.join(PROJECT_ROOT, "state", "_approval_response.json")
        os.makedirs(os.path.dirname(approval_file), exist_ok=True)
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump({
                "approved": approved,
                "notes": notes,
                "timestamp": datetime.now().isoformat(),
            }, f)

        self._send_json(200, {
            "status": "approved" if approved else "rejected",
            "notes": notes,
        })

    def _handle_approve_dag(self):
        """批准或拒绝 PM 的 DAG 执行计划（两阶段）。

        阶段一 — 开始审查：
          {"status": "reviewing", "notes": "我看看"}

        阶段二 — 做出决定：
          {"approved": true, "notes": "可以"}
          {"approved": false, "notes": "重新规划"}
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "无效的 JSON"})
            return

        state_dir = os.path.join(PROJECT_ROOT, "state")

        # 阶段一：确认审查
        if data.get("status") == "reviewing":
            ack_file = os.path.join(state_dir, "_dag_approval_ack.json")
            os.makedirs(os.path.dirname(ack_file), exist_ok=True)
            with open(ack_file, "w", encoding="utf-8") as f:
                json.dump({
                    "acknowledged": True,
                    "notes": data.get("notes", ""),
                    "timestamp": datetime.now().isoformat(),
                }, f)
            self._send_json(200, {"status": "reviewing", "message": "已确认，计时开始"})
            return

        # 阶段二：做出决定
        approved = data.get("approved")
        if approved is None:
            self._send_json(400, {"error": "请指定 approved: true/false 或 status: 'reviewing'"})
            return

        notes = data.get("notes", "")
        dec_file = os.path.join(state_dir, "_dag_approval_response.json")
        os.makedirs(os.path.dirname(dec_file), exist_ok=True)
        with open(dec_file, "w", encoding="utf-8") as f:
            json.dump({
                "approved": approved,
                "notes": notes,
                "timestamp": datetime.now().isoformat(),
            }, f)

        self._send_json(200, {
            "status": "approved" if approved else "rejected",
            "notes": notes,
        })

    # ── 辅助 ─────────────────────────────────────────

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors(self, code: int):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """将所有请求日志输出到 stderr（不影响 API 响应）。"""
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}\n")


# ═══════════════════════════════════════════════════════
# 后台异步任务执行器
# ═══════════════════════════════════════════════════════

def _run_async_task(task_id: str, task_desc: str, project_name: str,
                    provider: str | None, webhook_url: str | None):
    """在后台线程中运行 asyncio 事件循环。"""
    global _project_running

    # 子线程 stdout/stderr 可能恢复为 GBK，重新设为 UTF-8
    _set_utf8_stdio()
    try:
        from state_manager import init_project, MASTER_PATH, get_project
        from runner import run_project

        # 并发保护：检查是否有项目正在执行
        with _project_lock:
            if _project_running:
                print(f"✗ 已有项目正在执行，拒绝新任务 {task_id}")
                _set_task(task_id, {
                    **_get_task(task_id),
                    "status": "error",
                    "completed_at": datetime.now().isoformat(),
                    "error": "已有项目正在执行，请等待完成后重试",
                })
                if webhook_url:
                    _call_webhook(webhook_url, task_id, "error", "项目正在执行中")
                return
            _project_running = True

        # 断点续跑检测：如果 master.json 存在且项目未完成，直接恢复
        if MASTER_PATH.exists():
            try:
                existing = get_project()
                if existing.get("status") in ("in_progress",):
                    print(f"\n→ 检测到未完成的项目「{existing['name']}」，尝试断点恢复...")
                    result = asyncio.run(run_project(task_desc, provider=provider))
                    _set_task(task_id, {
                        **_get_task(task_id),
                        "status": "done",
                        "completed_at": datetime.now().isoformat(),
                        "result": result[:3000] if result else "",
                        "resumed": True,
                    })
                    if webhook_url:
                        _call_webhook(webhook_url, task_id, "done")
                    return
            except Exception as e:
                import logging
                logging.getLogger("server").warning("断点恢复失败（%s），将从头开始", e)

        # 正常启动：初始化新项目
        init_project(project_name)
        event_bus.emit("project_initialized", {"project_name": project_name, "task": task_desc[:120]})

        # 运行 DAG
        result = asyncio.run(run_project(task_desc, provider=provider))

        # 更新任务状态
        _set_task(task_id, {
            **_get_task(task_id),
            "status": "done",
            "completed_at": datetime.now().isoformat(),
            "result": result[:3000] if result else "",
        })
        event_bus.emit("task_completed", {"task_id": task_id, "project_name": project_name})

        # 如果有 webhook URL，通知 n8n
        if webhook_url:
            _call_webhook(webhook_url, task_id, "done")

    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        print(f"✗ 任务 {task_id} 执行失败：{e}\n{error_info}")

        _set_task(task_id, {
            **_get_task(task_id),
            "status": "error",
            "completed_at": datetime.now().isoformat(),
            "error": str(e),
            "traceback": error_info[-4000:],
        })
        event_bus.emit("task_error", {"task_id": task_id, "project_name": project_name,
                                       "error": str(e)})

        if webhook_url:
            _call_webhook(webhook_url, task_id, "error", str(e))

    finally:
        with _project_lock:
            _project_running = False


def _call_webhook(url: str, task_id: str, status: str, error: str = ""):
    """异步通知 n8n webhook 任务完成。"""
    try:
        import urllib.request
        payload = json.dumps({
            "task_id": task_id,
            "status": status,
            "error": error,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"⚠ 通知 webhook 失败：{e}")


# ═══════════════════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════════════════

def main():
    host = os.environ.get("AI_TEAM_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_TEAM_PORT", "8123"))

    # 启动前健康检查
    from health_check import preflight_check
    if not preflight_check(port=port):
        sys.exit(1)

    server = ThreadingHTTPServer((host, port), TeamHTTPHandler)

    print(f"╔══════════════════════════════════════════╗")
    print(f"║  AI 开发团队 — HTTP 服务器              ║")
    print(f"║══════════════════════════════════════════║")
    print(f"║  地址: http://{host}:{port}              ")
    print(f"║  服务:                                   ║")
    print(f"║    POST /run        提交开发任务               ║")
    print(f"║    GET  /status     项目状态                  ║")
    print(f"║    GET  /status/id  任务状态                  ║")
    print(f"║    GET  /events     SSE 实时事件流            ║")
    print(f"║    GET  /dashboard  实时看板页面               ║")
    print(f"║    GET  /api/state  JSON 状态快照             ║")
    print(f"║    POST /approve    人工审批                   ║")
    print(f"║    POST /approve-dag DAG 执行计划审批          ║")
    print(f"║    GET  /health     健康检查                   ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"n8n 集成示例:")
    print(f"  HTTP Request 节点 -> POST http://{host}:{port}/run")
    print(f"  Body: {{\"task\": \"实现登录功能\", \"provider\": \"claude\"}}")
    print(f"")
    print(f"📊 实时看板: http://{host}:{port}/dashboard")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
