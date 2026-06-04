"""操作日志记录工具"""

from __future__ import annotations

import json
from datetime import datetime

from flask import request

from db import get_db


def log_operation(
    user_id: int | None,
    action: str,
    target: str | None = None,
    detail: dict | None = None,
):
    """向 operation_logs 表写入一条操作日志（fire-and-forget）"""
    try:
        ip = request.remote_addr or ""
        ua = (request.headers.get("User-Agent") or "")[:500]
        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO operation_logs
                       (user_id, action, target, ip_address, user_agent, detail)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (user_id, action, target, ip, ua, detail_json),
                )
    except Exception:
        # 操作日志记录失败不应影响主流程
        pass
