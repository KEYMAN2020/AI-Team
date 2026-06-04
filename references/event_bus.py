"""
event_bus.py — 轻量级事件总线（SSE 实时推送用）
=================================================
server.py 和 runner.py 共同导入。
runner 在执行各阶段 emit() 事件，server 的 SSE 端点订阅并推给浏览器。
"""

import json
import threading
from datetime import datetime
from queue import Queue, Empty

_clients: list[Queue] = []
_lock = threading.Lock()
_log: list[str] = []          # 最近事件日志（最多 200 条），新客户端重放用
_log_lock = threading.Lock()
_MAX_LOG = 200


def subscribe() -> tuple[Queue, list[str]]:
    """
    新 SSE 客户端订阅事件流。
    返回 (queue, recent_events) — recent_events 用于重放历史。
    """
    q = Queue()
    with _lock:
        _clients.append(q)
    with _log_lock:
        replay = list(_log)  # 拷贝快照
    return q, replay


def unsubscribe(q: Queue):
    """客户端断开连接时清理。"""
    with _lock:
        if q in _clients:
            _clients.remove(q)


def emit(event: str, data: dict):
    """广播事件给所有已连接的 SSE 客户端。"""
    payload = {"event": event, "data": data, "ts": datetime.now().isoformat()}
    raw = json.dumps(payload, ensure_ascii=False)

    # 写入滚动日志（供新客户端重放）
    with _log_lock:
        _log.append(raw)
        if len(_log) > _MAX_LOG:
            _log[:50] = []  # 批量裁剪头部，保留最新

    # 广播给所有活跃客户端
    with _lock:
        dead = []
        for q in _clients:
            try:
                q.put_nowait(raw)
            except Exception:
                dead.append(q)
        for q in dead:
            if q in _clients:
                _clients.remove(q)


def format_sse(event_raw: str) -> str:
    """Format raw event payload as SSE protocol text."""
    try:
        obj = json.loads(event_raw)
        dat = json.dumps(obj, ensure_ascii=False)
        return "data: " + dat + "\n\n"
    except Exception:
        return "data: " + event_raw + "\n\n"
