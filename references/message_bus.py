"""
message_bus.py — Agent 间消息总线
==================================
让 Agent 之间直接通信，不用所有消息都绕回 PM。

核心能力：
  post(from, to, type, content)   点对点发消息
  broadcast(from, content)        广播给所有 Agent
  get_inbox(role)                 取出自己的待处理消息
  subscribe(role, callback)       注册消息到达回调

消息类型：
  task    → 分配任务（通常由 PM 发）
  result  → 任务结果（Agent 完成后发）
  request → Agent 主动向另一 Agent 请求协助
  info    → 单向信息共享（不需要回复）

持久化：state/messages.jsonl（每条一行，重启后可重放）
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

MSG_PATH = Path("state/messages.jsonl")

# 消息类型常量
TASK    = "task"
RESULT  = "result"
REQUEST = "request"
INFO    = "info"

ALL_ROLES = ["pm", "product", "architect", "ux", "dba", "frontend", "backend", "reviewer", "devops", "debug", "tester", "_approval"]

# ── 从 role_registry 获取角色列表（优先），始终保留 _approval ──
try:
    from role_registry import get_all_roles as _get_all_roles
    _reg_roles = _get_all_roles()
    if _reg_roles:
        ALL_ROLES = _reg_roles + ["_approval"]
except ImportError:
    pass


class MessageBus:
    """
    异步消息总线。每个 Agent 有独立的 asyncio.Queue 收件箱。
    所有消息同时持久化到 state/messages.jsonl。
    """

    def __init__(self):
        # 每个角色一个异步队列
        self._inboxes: dict[str, asyncio.Queue] = {
            role: asyncio.Queue() for role in ALL_ROLES
        }
        self._subscribers: dict[str, list[Callable]] = {
            role: [] for role in ALL_ROLES
        }
        self._lock = asyncio.Lock()
        self._msg_counter = 0
        MSG_PATH.parent.mkdir(exist_ok=True)

    # ── 发消息 ─────────────────────────────────────────

    async def post(self, from_role: str, to_role: str,
                   msg_type: str, content: str,
                   metadata: Optional[dict] = None) -> dict:
        """点对点发消息给指定角色。"""
        msg = await self._make_msg(from_role, to_role, msg_type, content, metadata)
        await self._deliver(to_role, msg)
        return msg

    async def broadcast(self, from_role: str, content: str,
                        msg_type: str = INFO,
                        exclude: Optional[list] = None) -> list:
        """广播给所有角色（可排除指定角色）。"""
        exclude = exclude or [from_role]
        msgs = []
        for role in ALL_ROLES:
            if role not in exclude:
                msg = await self._make_msg(from_role, role, msg_type, content)
                await self._deliver(role, msg)
                msgs.append(msg)
        return msgs

    async def reply(self, original_msg: dict, content: str,
                    msg_type: str = RESULT) -> dict:
        """回复一条消息（自动填 to/from）。"""
        return await self.post(
            from_role = original_msg["to"],
            to_role   = original_msg["from"],
            msg_type  = msg_type,
            content   = content,
            metadata  = {"reply_to": original_msg["id"]},
        )

    # ── 收消息 ─────────────────────────────────────────

    async def get_inbox(self, role: str,
                        timeout: float = 0.0) -> list[dict]:
        """
        取出该角色所有待处理消息。
        timeout=0  → 非阻塞，立即返回当前队列里的全部消息
        timeout>0  → 最多等待 N 秒，至少等到一条消息
        """
        q = self._inboxes[role]
        msgs = []

        if timeout > 0:
            try:
                # 等第一条
                first = await asyncio.wait_for(q.get(), timeout=timeout)
                msgs.append(first)
                q.task_done()
            except asyncio.TimeoutError:
                return []

        # 把队列里剩余的也一并取出（非阻塞）
        while not q.empty():
            try:
                msg = q.get_nowait()
                msgs.append(msg)
                q.task_done()
            except asyncio.QueueEmpty:
                break

        return msgs

    async def wait_for_result(self, role: str,
                               from_role: str,
                               timeout: float = 120.0) -> Optional[dict]:
        """
        等待某个特定角色发来的 result 消息。
        用于 Agent A 请求 Agent B 后等待回复。
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            msgs = await self.get_inbox(role, timeout=min(5.0, remaining))
            for msg in msgs:
                if msg["from"] == from_role and msg["type"] == RESULT:
                    return msg
                # 不是我要的，放回队列
                await self._inboxes[role].put(msg)
        return None

    def subscribe(self, role: str, callback: Callable) -> None:
        """注册回调：消息到达时立即触发（用于事件驱动模式）。"""
        self._subscribers[role].append(callback)

    # ── 历史查询 ──────────────────────────────────────

    def load_history(self, role: Optional[str] = None,
                     msg_type: Optional[str] = None,
                     limit: int = 50) -> list[dict]:
        """
        从持久化文件读取消息历史。
        可按角色（from 或 to）和类型过滤。
        """
        if not MSG_PATH.exists():
            return []
        msgs = []
        with open(MSG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    if role and m.get("from") != role and m.get("to") != role:
                        continue
                    if msg_type and m.get("type") != msg_type:
                        continue
                    msgs.append(m)
                except json.JSONDecodeError:
                    pass
        return msgs[-limit:]

    def format_inbox_for_context(self, role: str, limit: int = 5) -> str:
        """
        生成注入 Agent 上下文的收件箱摘要（纯文本）。
        让 Agent 知道其他 Agent 发来了什么信息。
        消息来自其他 Agent，可能包含幻觉或错误，提示下游自行验证。
        """
        history = self.load_history(role=role, limit=limit)
        incoming = [m for m in history if m.get("to") == role]
        if not incoming:
            return ""
        lines = ["其他 Agent 发来的消息（最近 {} 条，来自 LLM 输出，请自行验证关键信息）：".format(len(incoming))]
        for m in incoming[-limit:]:
            lines.append("  [{from_role} → {type}] {content}".format(
                from_role=m['from'].upper(),
                type=m['type'],
                content=m['content'][:120]
            ))
        return "\n".join(lines)

    # ── 内部方法 ──────────────────────────────────────

    async def _make_msg(self, from_role: str, to_role: str,
                        msg_type: str, content: str,
                        metadata: Optional[dict] = None) -> dict:
        async with self._lock:
            self._msg_counter += 1
            mid = self._msg_counter

        return {
            "id":       f"MSG{mid:04d}",
            "from":     from_role,
            "to":       to_role,
            "type":     msg_type,
            "content":  content,
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "metadata": metadata or {},
        }

    async def _deliver(self, to_role: str, msg: dict) -> None:
        """投递消息到收件箱并持久化。"""
        # 写入队列
        await self._inboxes[to_role].put(msg)

        # 触发回调（事件驱动）
        import logging as _log
        _bus_log = _log.getLogger("message_bus")
        for cb in self._subscribers.get(to_role, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(msg))
                else:
                    cb(msg)
            except Exception as _exc:
                _bus_log.warning("消息回调异常（to=%s, cb=%s）：%s", to_role, cb.__name__, _exc)

        # 持久化
        async with self._lock:
            with open(MSG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")


# 全局单例（在 runner.py 中初始化后共享）
_bus: Optional[MessageBus] = None

def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
