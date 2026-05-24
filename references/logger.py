"""
logger.py — 统一结构化日志
============================
提供 StructuredLogger，将事件写入 JSONL 文件同时输出到 stdout。

每条日志包含：
  - ts: 时间戳
  - project_id: 项目标识
  - role: 角色名（如适用）
  - dispatch_id: 调度 ID（task_id）
  - phase: planning / executing / approval / integrating
  - event: task_started / task_completed / approval_pending / sub_request_spawned / error

用法：
  from logger import get_logger
  slog = get_logger("proj_001")
  slog.log("info", role="frontend", dispatch_id="T003",
           phase="executing", event="task_completed",
           summary="前端模块已完成", tokens=12345)

查询（事后）：
  jq '.role == "frontend"' logs/proj_001.jsonl
  jq 'select(.event == "error")' logs/proj_001.jsonl
"""

import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 标准 logging（兼容已有代码） ──────────────────────

class _SafeStderrHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except (ValueError, OSError):
            pass  # stderr closed, silently ignore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[_SafeStderrHandler(sys.stderr)],
)

# ── JSONL 结构化日志 ─────────────────────────────────


class StructuredLogger:
    """结构化日志，同时输出到 stdout 和 JSONL 文件。"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._log_dir = Path(os.environ.get(
            "AI_TEAM_LOG_DIR",
            str(Path(__file__).resolve().parent.parent / "logs"),
        ))
        self._log_file = self._log_dir / f"{project_id}.jsonl"
        self._lock = threading.Lock()

    def log(self, level: str, event: str, **fields):
        """写入一条结构化日志。

        level: info / warn / error
        event: task_started / task_completed / approval_pending /
               sub_request_spawned / error / ...
        fields: role, dispatch_id, phase, summary, tokens, error, ...
        """
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "project_id": self.project_id,
            "level": level,
            "event": event,
            **fields,
        }

        # 写入 JSONL 文件
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 磁盘写入失败不阻塞主逻辑

        # 同时输出到 stdout（人类可读格式）
        role = fields.get("role", "")
        dispatch = fields.get("dispatch_id", "")
        phase = fields.get("phase", "")
        summary = fields.get("summary", "")
        error = fields.get("error", "")

        prefix = f"[{record['ts']}]"
        tag = f"[{role}]" if role else ""
        did = f"[{dispatch}]" if dispatch else ""
        ph = f"({phase})" if phase else ""

        parts = [prefix, tag, did, ph, event]
        if summary:
            detail = summary[:120] + ("..." if len(summary) > 120 else "")
            parts.append(f"- {detail}")
        if error:
            parts.append(f"| error={error[:200]}")
        print(" ".join(p for p in parts if p), file=sys.stderr)


# ── 全局实例管理 ─────────────────────────────────────

_slog: Optional[StructuredLogger] = None
_slog_lock = threading.Lock()


def init_logger(project_id: str) -> StructuredLogger:
    """初始化或切换当前项目的结构化日志。"""
    global _slog
    with _slog_lock:
        _slog = StructuredLogger(project_id)
    return _slog


def get_logger() -> StructuredLogger:
    """获取当前结构化日志实例（未初始化时创建默认）。"""
    global _slog
    if _slog is None:
        with _slog_lock:
            if _slog is None:
                _slog = StructuredLogger("default")
    return _slog
