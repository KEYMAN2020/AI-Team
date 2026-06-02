# AI-TeaM HTTP Server
# ====================
# Cherry Studio锛堜汉绫?I/O锛夆啋 n8n锛堝伐浣滄祦缂栨帓锛夆啋 server.py 鈫?LLM API锛堝 Agent 鎵ц锛?#
# 绔粸锛?#   POST /run         鎻愪氦椤圭洰浠诲姟锛岃繑鍥?task_id锛堝紓姝ユ墽琛岋級
#   GET  /status      鏌ョ湅褰撳墠椤圭洰鍜屾墍鏈夎鑹茬姸鎬?#   GET  /health      鍋ュ悍妫€鏌?#   POST /approve     鎵瑰噯绛夊緟涓殑浜哄伐瀹℃壒鑺傜偣
#
# 鐢ㄦ硶锛?#   python start_server.py   # 鎺ㄨ崘锛堣嚜鍔ㄦ竻闄や唬鐞嗭紝keys 鏉ヨ嚜鐜鍙橀噺锛?#   python server.py         # 鐩存帴鍚姩锛堥渶鍏堣濂界幆澧冨彉閲忥級
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

# 鈹€鈹€ 浜嬩欢鎬荤嚎锛圫SE 瀹炴椂鎺ㄩ€侊級 鈹€鈹€
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "references"))
import event_bus

# 鈹€鈹€ 娓呴櫎浠ｇ悊锛堥伩鍏?httpx/OpenAI SDK 璧颁唬鐞嗗鑷磋繛鎺ラ棶棰橈級鈹€鈹€
# API Key 閫氳繃绯荤粺鐜鍙橀噺娉ㄥ叆锛屽弬瑙?.env.example
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

# Safe print 鈥?prevents "I/O operation on closed file" crash when asyncio
# closes stdout/stderr on Windows (ProactorEventLoop issue)
import builtins as _builtins
_original_print = _builtins.print
def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except (ValueError, OSError, UnicodeEncodeError):
        # UnicodeEncodeError: 瀛愮嚎绋?stdout 鍙兘鏄?GBK锛宔moji 缂栫爜澶辫触鏃堕潤榛樿烦杩?        pass
_builtins.print = _safe_print

# 灏?references/ 鍔犲叆 path锛屼娇鍚勬ā鍧楀彲鐩存帴瀵煎叆
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "references"))

# 鈹€鈹€ 浠诲姟绠＄悊 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 鍐呭瓨涓殑浠诲姟鐘舵€佸瓨鍌紙n8n 杞鐢級
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
# 骞跺彂淇濇姢锛氭爣璁板綋鍓嶆槸鍚︽湁椤圭洰姝ｅ湪鎵ц锛岄槻姝袱涓?/run 璇锋眰鍐茬獊
_project_running = False
_project_lock = threading.Lock()


def _get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        return _tasks.get(task_id)


def _set_task(task_id: str, data: dict) -> None:
    with _tasks_lock:
        _tasks[task_id] = data


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# HTTP Handler
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
class TeamHTTPHandler(BaseHTTPRequestHandler):
    """涓?n8n 鎻愪緵 HTTP API 鐨勮姹傚鐞嗗櫒銆?""

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

    # 鈹€鈹€ Handlers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _handle_health(self):
        self._send_json(200, {
            "status": "ok",
            "version": "2.0",
            "timestamp": datetime.now().isoformat(),
        })

    def _handle_status(self):
        """杩斿洖褰撳墠椤圭洰鐨勫畬鏁寸姸鎬侊紙浠?master.json 璇诲彇锛夈€?""
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
                "message": "鏈垵濮嬪寲椤圭洰锛岃鍏?POST /run 鎻愪氦浠诲姟",
            })

    def _handle_task_status(self, task_id: str):
        """鏌ヨ鏌愪釜寮傛浠诲姟鐨勬墽琛岀姸鎬併€?""
        task = _get_task(task_id)
        if not task:
            self._send_json(404, {"error": f"Task {task_id} not found"})
            return

        # 濡傛灉浠诲姟宸插畬鎴愶紝椤轰究浠?state 璇诲彇鏈€鏂伴」鐩俊鎭?        result = dict(task)
        if task.get("status") in ("done", "partial"):
            try:
                from state_manager import get_project
                result["project"] = get_project()
            except Exception:
                pass

        self._send_json(200, result)

    def _handle_sse(self):
        """SSE 绔偣鈥旀帹閫佸疄鏃朵簨浠剁粰鍓嶇鐪嬫澘銆?""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q, replay = event_bus.subscribe()
        try:
            # 鍏堥噸鏀惧巻鍙蹭簨浠讹紙璁╂柊椤甸潰鐪嬪埌宸插彂鐢熺殑杩涘害锛?            for raw in replay:
                sse_text = event_bus.format_sse(raw)
                try:
                    self.wfile.write(sse_text.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    return

            # 鎸佺画鎺ㄩ€佹柊浜嬩欢
            while True:
                try:
                    raw = q.get(timeout=15)  # 15s 瓒呮椂鐢ㄤ簬鍙戝績璺?                    sse_text = event_bus.format_sse(raw)
                    self.wfile.write(sse_text.encode("utf-8"))
                    self.wfile.flush()
                except Empty:
                    # 蹇冭烦 keepalive
                    try:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                    except Exception:
                        return
        finally:
            event_bus.unsubscribe(q)

    def _handle_dashboard(self):
        """鎻愪緵瀹炴椂鐪嬫澘 HTML銆?""
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
        """JSON 鎺ュ彛鈥旇疆璇㈠厹搴曠敤锛堣繑鍥?master.json 蹇収锛夈€?""
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
            self._send_json(200, {"project": None, "message": "鏃犳椿鍔ㄩ」鐩?})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_run(self):
        """鎻愪氦涓€涓」鐩紑鍙戜换鍔★紝寮傛鎵ц銆?
        璇锋眰浣擄紙JSON锛夛細
          {
            "task": "瀹炵幇鐢ㄦ埛娉ㄥ唽鐧诲綍鍔熻兘锛屽惈 JWT 璁よ瘉",
            "provider": "claude",          // 鍙€夛紝榛樿鐢?ACTIVE_PROVIDER
            "project_name": "鐢ㄦ埛妯″潡",      // 鍙€?            "webhook_url": "https://..."    // 鍙€夛紝n8n 鍥炶皟鍦板潃
          }

        杩斿洖锛?          { "task_id": "proj_20260510_1430", "status": "running" }
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "鏃犳晥鐨?JSON"})
            return

        task_desc = data.get("task", "").strip()
        if not task_desc:
            self._send_json(400, {"error": "缂哄皯 task 瀛楁"})
            return

        provider = data.get("provider")
        project_name = data.get("project_name", f"n8n_{datetime.now().strftime('%m%d_%H%M')}")
        webhook_url = data.get("webhook_url")
        clean = data.get("clean", False)  # 芒聠聬 忙聳掳氓垄聻茂录職氓录潞氓聢露忙赂聟莽聬聠忙聴搂莽聤露忙聙聛

        # 鍦ㄥ悗鍙扮嚎绋嬩腑鎵ц
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
            args=(task_id, task_desc, project_name, provider, webhook_url, clean),
            daemon=True,
        )
        thread.start()

        self._send_json(202, {
            "task_id": task_id,
            "status": "running",
            "message": "浠诲姟宸叉彁浜わ紝璇疯疆璇?GET /status/{task_id} 鑾峰彇缁撴灉",
        })

    def _handle_approve(self):
        """鎵瑰噯绛夊緟涓殑浜哄伐瀹℃壒鑺傜偣锛堜袱闃舵娴佺▼锛夈€?
        闃舵涓€ 鈥?寮€濮嬪鏌ワ紙纭宸茬湅鍒帮級锛?          {"status": "reviewing", "notes": "鎴戝紑濮嬪浜?}

        闃舵浜?鈥?鍋氬嚭鍐冲畾锛?          {"approved": true, "notes": "鏂规娌￠棶棰?}
          {"approved": false, "notes": "鏂规涓嶅悎閫?}
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "鏃犳晥鐨?JSON"})
            return

        # 闃舵涓€锛氱敤鎴风‘璁ゅ凡鐪嬪埌锛屽紑濮嬪鏌?        if data.get("status") == "reviewing":
            ack_file = os.path.join(PROJECT_ROOT, "state", "_approval_ack.json")
            os.makedirs(os.path.dirname(ack_file), exist_ok=True)
            with open(ack_file, "w", encoding="utf-8") as f:
                json.dump({
                    "acknowledged": True,
                    "notes": data.get("notes", ""),
                    "timestamp": datetime.now().isoformat(),
                }, f)
            self._send_json(200, {"status": "reviewing", "message": "宸茬‘璁わ紝璁℃椂寮€濮?})
            return

        # 闃舵浜岋細鐢ㄦ埛鍋氬嚭鍐冲畾
        approved = data.get("approved")
        if approved is None:
            self._send_json(400, {"error": "璇锋寚瀹?approved: true/false 鎴?status: 'reviewing'"})
            return

        notes = data.get("notes", "閫氳繃 HTTP API 鎵瑰噯")

        # 灏嗗鎵圭粨鏋滃啓鍏ヤ竴涓复鏃舵枃浠讹紝runner.py 鐨?_request_human_approval 浼氳鍙?        approval_file = os.path.join(PROJECT_ROOT, "state", "_approval_response.json")
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
        """鎵瑰噯鎴栨嫆缁?PM 鐨?DAG 鎵ц璁″垝锛堜袱闃舵锛夈€?
        闃舵涓€ 鈥?寮€濮嬪鏌ワ細
          {"status": "reviewing", "notes": "鎴戠湅鐪?}

        闃舵浜?鈥?鍋氬嚭鍐冲畾锛?          {"approved": true, "notes": "鍙互"}
          {"approved": false, "notes": "閲嶆柊瑙勫垝"}
        """
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "鏃犳晥鐨?JSON"})
            return

        state_dir = os.path.join(PROJECT_ROOT, "state")

        # 闃舵涓€锛氱‘璁ゅ鏌?        if data.get("status") == "reviewing":
            ack_file = os.path.join(state_dir, "_dag_approval_ack.json")
            os.makedirs(os.path.dirname(ack_file), exist_ok=True)
            with open(ack_file, "w", encoding="utf-8") as f:
                json.dump({
                    "acknowledged": True,
                    "notes": data.get("notes", ""),
                    "timestamp": datetime.now().isoformat(),
                }, f)
            self._send_json(200, {"status": "reviewing", "message": "宸茬‘璁わ紝璁℃椂寮€濮?})
            return

        # 闃舵浜岋細鍋氬嚭鍐冲畾
        approved = data.get("approved")
        if approved is None:
            self._send_json(400, {"error": "璇锋寚瀹?approved: true/false 鎴?status: 'reviewing'"})
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

    # 鈹€鈹€ 杈呭姪 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

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
        """灏嗘墍鏈夎姹傛棩蹇楄緭鍑哄埌 stderr锛堜笉褰卞搷 API 鍝嶅簲锛夈€?""
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}\n")


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 鍚庡彴寮傛浠诲姟鎵ц鍣?# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
def _run_async_task(task_id: str, task_desc: str, project_name: str,
                    provider: str | None, webhook_url: str | None,
                    clean: bool = False):
    """鍦ㄥ悗鍙扮嚎绋嬩腑杩愯 asyncio 浜嬩欢寰幆銆?""
    global _project_running

    # 瀛愮嚎绋?stdout/stderr 鍙兘鎭㈠涓?GBK锛岄噸鏂拌涓?UTF-8
    _set_utf8_stdio()
    try:
        from state_manager import init_project, MASTER_PATH, get_project
        from runner import run_project

        # 骞跺彂淇濇姢锛氭鏌ユ槸鍚︽湁椤圭洰姝ｅ湪鎵ц
        with _project_lock:
            if _project_running:
                print(f"鉁?宸叉湁椤圭洰姝ｅ湪鎵ц锛屾嫆缁濇柊浠诲姟 {task_id}")
                _set_task(task_id, {
                    **_get_task(task_id),
                    "status": "error",
                    "completed_at": datetime.now().isoformat(),
                    "error": "宸叉湁椤圭洰姝ｅ湪鎵ц锛岃绛夊緟瀹屾垚鍚庨噸璇?,
                })
                if webhook_url:
                    _call_webhook(webhook_url, task_id, "error", "椤圭洰姝ｅ湪鎵ц涓?)
                return
            _project_running = True

        # ---- cleanup old state when clean=True ------------------------------
        if MASTER_PATH.exists() and clean:
            import shutil
            from pathlib import Path
            state_dir = MASTER_PATH.parent
            print(f"[clean] cleaning old state: {state_dir}")
            for d in [state_dir / "snapshots", state_dir / "summaries"]:
                if d.exists():
                    shutil.rmtree(d)
            for f in state_dir.glob("_*.json"):
                f.unlink()
            for fn in ["messages.jsonl"]:
                fp = state_dir / fn
                if fp.exists():
                    fp.unlink()
            if MASTER_PATH.exists():
                MASTER_PATH.unlink()
                print("  [clean] removed master.json, starting fresh")
            outputs_dir = Path("/app/outputs")
            if outputs_dir.exists():
                for f in outputs_dir.iterdir():
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f)
            print("  [clean] state cleanup complete")

        # 鏂偣缁窇妫€娴嬶細濡傛灉 master.json 瀛樺湪涓旈」鐩湭瀹屾垚锛岀洿鎺ユ仮澶?        if MASTER_PATH.exists():
            try:
                existing = get_project()
                if existing.get("status") in ("in_progress",):
                    print(f"\n鈫?妫€娴嬪埌鏈畬鎴愮殑椤圭洰銆寋existing['name']}銆嶏紝灏濊瘯鏂偣鎭㈠...")
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
                logging.getLogger("server").warning("鏂偣鎭㈠澶辫触锛?s锛夛紝灏嗕粠澶村紑濮?, e)

        # 姝ｅ父鍚姩锛氬垵濮嬪寲鏂伴」鐩?        init_project(project_name)
        event_bus.emit("project_initialized", {"project_name": project_name, "task": task_desc[:120]})

        # 杩愯 DAG
        result = asyncio.run(run_project(task_desc, provider=provider))

        # 鏇存柊浠诲姟鐘舵€?        _set_task(task_id, {
            **_get_task(task_id),
            "status": "done",
            "completed_at": datetime.now().isoformat(),
            "result": result[:3000] if result else "",
        })
        event_bus.emit("task_completed", {"task_id": task_id, "project_name": project_name})

        # 濡傛灉鏈?webhook URL锛岄€氱煡 n8n
        if webhook_url:
            _call_webhook(webhook_url, task_id, "done")

    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        print(f"鉁?浠诲姟 {task_id} 鎵ц澶辫触锛歿e}\n{error_info}")

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
    """寮傛閫氱煡 n8n webhook 浠诲姟瀹屾垚銆?""
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
        print(f"鈿?閫氱煡 webhook 澶辫触锛歿e}")


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?# 鍚姩鍏ュ彛
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
def main():
    host = os.environ.get("AI_TEAM_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_TEAM_PORT", "8123"))

    # 鍚姩鍓嶅仴搴锋鏌?    from health_check import preflight_check
    if not preflight_check(port=port):
        sys.exit(1)

    server = ThreadingHTTPServer((host, port), TeamHTTPHandler)

    print(f"鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽")
    print(f"鈺? AI 寮€鍙戝洟闃?鈥?HTTP 鏈嶅姟鍣?             鈺?)
    print(f"鈺戔晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晳")
    print(f"鈺? 鍦板潃: http://{host}:{port}              ")
    print(f"鈺? 鏈嶅姟:                                   鈺?)
    print(f"鈺?   POST /run        鎻愪氦寮€鍙戜换鍔?              鈺?)
    print(f"鈺?   GET  /status     椤圭洰鐘舵€?                 鈺?)
    print(f"鈺?   GET  /status/id  浠诲姟鐘舵€?                 鈺?)
    print(f"鈺?   GET  /events     SSE 瀹炴椂浜嬩欢娴?           鈺?)
    print(f"鈺?   GET  /dashboard  瀹炴椂鐪嬫澘椤甸潰               鈺?)
    print(f"鈺?   GET  /api/state  JSON 鐘舵€佸揩鐓?            鈺?)
    print(f"鈺?   POST /approve    浜哄伐瀹℃壒                   鈺?)
    print(f"鈺?   POST /approve-dag DAG 鎵ц璁″垝瀹℃壒          鈺?)
    print(f"鈺?   GET  /health     鍋ュ悍妫€鏌?                  鈺?)
    print(f"鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆")
    print(f"n8n 闆嗘垚绀轰緥:")
    print(f"  HTTP Request 鑺傜偣 -> POST http://{host}:{port}/run")
    print(f"  Body: {{\"task\": \"瀹炵幇鐧诲綍鍔熻兘\", \"provider\": \"claude\"}}")
    print(f"")
    print(f"馃搳 瀹炴椂鐪嬫澘: http://{host}:{port}/dashboard")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n鏈嶅姟鍣ㄥ凡鍋滄銆?)
        server.server_close()


if __name__ == "__main__":
    main()
