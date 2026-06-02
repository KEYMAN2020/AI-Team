"""
event_bus.py 鈥?杞婚噺绾т簨浠舵€荤嚎锛圫SE 瀹炴椂鎺ㄩ€佺敤锛?=================================================
server.py 鍜?runner.py 鍏卞悓瀵煎叆銆?runner 鍦ㄦ墽琛屽悇闃舵 emit() 浜嬩欢锛宻erver 鐨?SSE 绔偣璁㈤槄骞舵帹缁欐祻瑙堝櫒銆?"""

import json
import threading
from datetime import datetime
from queue import Queue, Empty

_clients: list[Queue] = []
_lock = threading.Lock()
_log: list[str] = []          # 鏈€杩戜簨浠舵棩蹇楋紙鏈€澶?200 鏉★級锛屾柊瀹㈡埛绔噸鏀剧敤
_log_lock = threading.Lock()
_MAX_LOG = 200


def subscribe() -> tuple[Queue, list[str]]:
    """
    鏂?SSE 瀹㈡埛绔闃呬簨浠舵祦銆?    杩斿洖 (queue, recent_events) 鈥?recent_events 鐢ㄤ簬閲嶆斁鍘嗗彶銆?    """
    q = Queue()
    with _lock:
        _clients.append(q)
    with _log_lock:
        replay = list(_log)  # 鎷疯礉蹇収
    return q, replay


def unsubscribe(q: Queue):
    """瀹㈡埛绔柇寮€杩炴帴鏃舵竻鐞嗐€?""
    with _lock:
        if q in _clients:
            _clients.remove(q)


def emit(event: str, data: dict):
    """骞挎挱浜嬩欢缁欐墍鏈夊凡杩炴帴鐨?SSE 瀹㈡埛绔€?""
    payload = {"event": event, "data": data, "ts": datetime.now().isoformat()}
    raw = json.dumps(payload, ensure_ascii=False)

    # 鍐欏叆婊氬姩鏃ュ織锛堜緵鏂板鎴风閲嶆斁锛?    with _log_lock:
        _log.append(raw)
        if len(_log) > _MAX_LOG:
            _log[:50] = []  # 鎵归噺瑁佸壀澶撮儴锛屼繚鐣欐渶鏂?
    # 骞挎挱缁欐墍鏈夋椿璺冨鎴风
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
