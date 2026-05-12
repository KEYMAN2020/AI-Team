"""
circuit_breaker.py — API 调用熔断器
=====================================
防止 API key 失效或模型限流时无限重试烧 Token。

核心逻辑：
  - 在时间窗口内记录失败次数
  - 超过阈值写入标志文件 state/CIRCUIT_OPEN.flag
  - 熔断后所有 call_role() 调用直接抛异常，不发 HTTP 请求
  - 人工修复后删除标志文件即可恢复

用法：
  from circuit_breaker import CircuitBreaker
  cb = CircuitBreaker()
  if cb.is_open():
      raise RuntimeError("熔断器已打开")
  ...
  cb.record_failure("frontend", str(e))
  cb.record_success()
"""

import json
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from threading import Lock


class CircuitBreaker:
    """API 调用熔断器，线程安全。"""

    def __init__(self, max_failures: int = 5, window_seconds: int = 60):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: deque = deque()
        self._lock = Lock()
        self.flag_file = Path(os.environ.get(
            "AI_TEAM_STATE_DIR",
            str(Path(__file__).resolve().parent.parent / "state")
        )) / "CIRCUIT_OPEN.flag"

    def record_failure(self, role: str, error: str):
        """记录一次失败。窗口内超过阈值自动熔断。"""
        now = time.time()
        with self._lock:
            self._failures.append((now, role, error))
            # 清理窗口外的旧记录
            while self._failures and self._failures[0][0] < now - self.window:
                self._failures.popleft()
            if len(self._failures) >= self.max_failures:
                self._write_flag(role, error)

    def record_success(self, role: str = ""):
        """记录一次成功，只清该角色的失败记录（不影响其他角色）。"""
        with self._lock:
            if role:
                self._failures = deque(
                    (ts, r, err) for ts, r, err in self._failures if r != role
                )
            else:
                self._failures.clear()

    def is_open(self) -> bool:
        """检查熔断器是否打开（任何后续调用应立即拒绝）。"""
        if not self.flag_file.exists():
            return False
        # 读一下内容，记录日志用
        try:
            data = json.loads(self.flag_file.read_text(encoding="utf-8"))
            # 如果标志文件超过 30 分钟，自动清除（给人时间修复）
            opened_at = data.get("opened_at", "")
            if opened_at:
                try:
                    opened_ts = datetime.fromisoformat(opened_at).timestamp()
                    if time.time() - opened_ts > 1800:  # 30 分钟
                        self.flag_file.unlink(missing_ok=True)
                        with self._lock:
                            self._failures.clear()
                        return False
                except (ValueError, OSError):
                    pass
        except (json.JSONDecodeError, KeyError, OSError):
            pass
        return True

    def _write_flag(self, trigger_role: str, last_error: str):
        """写入熔断标志文件。"""
        self.flag_file.parent.mkdir(parents=True, exist_ok=True)
        # 截断错误信息，避免文件过大
        self.flag_file.write_text(json.dumps({
            "opened_at": datetime.now().isoformat(),
            "trigger_role": trigger_role,
            "last_error": last_error[:500],
            "recent_failures": [
                {
                    "time": datetime.fromtimestamp(ts).isoformat(),
                    "role": r,
                    "error": err[:200],
                }
                for ts, r, err in self._failures
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self):
        """手动重置熔断器（删除标志文件并清空计数）。"""
        self.flag_file.unlink(missing_ok=True)
        with self._lock:
            self._failures.clear()

    def reason(self) -> str:
        """返回熔断原因（用于日志或 API 响应）。"""
        if not self.flag_file.exists():
            return ""
        try:
            data = json.loads(self.flag_file.read_text(encoding="utf-8"))
            fail_count = len(data.get("recent_failures", []))
            return (
                f"熔断器已触发 — {data.get('trigger_role','?')} "
                f"角色连续失败 {fail_count} 次，"
                f"最后错误：{data.get('last_error','')[:200]}。"
                f"请检查 API key 或网络后删除 {self.flag_file} 恢复。"
            )
        except Exception as e:
            return f"熔断器已触发，请检查 {self.flag_file}（读取原因失败：{e}）"


# ── 全局单例 ──────────────────────────────────────

_breaker: CircuitBreaker | None = None


def get_breaker() -> CircuitBreaker:
    """获取全局熔断器实例。"""
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreaker()
    return _breaker
