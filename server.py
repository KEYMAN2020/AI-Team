"""
server.py — n8n HTTP 集成入口
=================================
为 AI 开发团队提供 HTTP API，供 n8n 工作流调用。

架构：
  Cherry Studio（人类 I/O）→ n8n（工作流编排）→ server.py → Claude API（多 Agent 执行）

端點：
  POST /run         提交项目任务，返回 task_id（异步执行）
  GET  /status      查看当前项目和所有角色状态
  GET  /health      健康检查
  POST /approve     批准等待中的人工审批节点

用法：
  # 启动服务器（默认 127.0.0.1:8123）
  python server.py

  # n8n HTTP Request 节点 -> POST http://localhost:8123/run
  # Body: {"task": "实现用户注册登录功能"}
"""

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# 将 references/ 加入 path，使各模块可直接导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "references"))

# ── 任务管理 ──────────────────────────────────────────
# 内存中的任务状态存储（n8n 轮询用）
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


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
    try:
        from state_manager import init_project, MASTER_PATH, get_project
        from runner import run_project

        os.chdir(PROJECT_ROOT)

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

        # 运行 DAG
        result = asyncio.run(run_project(task_desc, provider=provider))

        # 更新任务状态
        _set_task(task_id, {
            **_get_task(task_id),
            "status": "done",
            "completed_at": datetime.now().isoformat(),
            "result": result[:3000] if result else "",
        })

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
            "traceback": error_info[-2000:],
        })

        if webhook_url:
            _call_webhook(webhook_url, task_id, "error", str(e))


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

    server = HTTPServer((host, port), TeamHTTPHandler)

    print(f"╔══════════════════════════════════════════╗")
    print(f"║  AI 开发团队 — HTTP 服务器              ║")
    print(f"║══════════════════════════════════════════║")
    print(f"║  地址: http://{host}:{port}              ")
    print(f"║  服务:                                   ║")
    print(f"║    POST /run        提交开发任务            ║")
    print(f"║    GET  /status     项目状态               ║")
    print(f"║    GET  /status/id  任务状态               ║")
    print(f"║    POST /approve    人工审批                ║")
    print(f"║    POST /approve-dag DAG 执行计划审批       ║")
    print(f"║    GET  /health     健康检查                ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"n8n 集成示例:")
    print(f"  HTTP Request 节点 -> POST http://{host}:{port}/run")
    print(f"  Body: {{\"task\": \"实现登录功能\", \"provider\": \"claude\"}}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
