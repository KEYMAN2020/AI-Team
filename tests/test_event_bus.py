"""
test_event_bus.py — 事件总线单元测试
"""
import json
import pytest
from queue import Queue
from references.event_bus import subscribe, unsubscribe, emit, format_sse


class TestEventBus:
    """事件总线核心功能测试"""

    def test_subscribe_returns_queue(self):
        """subscribe() 应返回 Queue 和历史的元组"""
        q, replay = subscribe()
        assert isinstance(q, Queue)
        assert isinstance(replay, list)
        unsubscribe(q)

    def test_subscribe_replay_recent_events(self):
        """新订阅者应收到重放的历史事件"""
        q1, _ = subscribe()
        emit("test_event", {"msg": "hello"})
        q2, replay = subscribe()
        assert len(replay) >= 1
        parsed = json.loads(replay[-1])
        assert parsed["event"] == "test_event"
        assert parsed["data"]["msg"] == "hello"
        unsubscribe(q1)
        unsubscribe(q2)

    def test_unsubscribe_removes_queue(self):
        """unsubscribe() 应从客户端列表移除"""
        q, _ = subscribe()
        assert q is not None
        unsubscribe(q)
        # 取消订阅后 emit 不应再发给它
        emit("test", {"x": 1})
        assert q.empty()

    def test_emit_broadcasts_to_all_clients(self):
        """emit() 应广播给所有订阅客户端"""
        q1, _ = subscribe()
        q2, _ = subscribe()
        emit("broadcast", {"num": 42})

        msg1 = q1.get(timeout=1)
        msg2 = q2.get(timeout=1)
        assert json.loads(msg1)["event"] == "broadcast"
        assert json.loads(msg2)["event"] == "broadcast"
        assert json.loads(msg1)["data"]["num"] == 42
        unsubscribe(q1)
        unsubscribe(q2)

    def test_emit_removes_dead_clients(self):
        """emit() 应自动清理断开连接的客户端"""
        q, _ = subscribe()
        # 关闭 queue（模拟客户端断开）
        q.put = lambda x: (_ for _ in ()).throw(Exception("dead"))
        # 不应抛异常
        try:
            emit("test", {"x": 1})
        except Exception:
            pytest.fail("emit() 不应因死客户端而抛异常")

    def test_format_sse_valid_json(self):
        """format_sse() 应正确格式化 SSE 协议文本"""
        raw = json.dumps({"event": "task_done", "data": {"status": "ok"}})
        sse = format_sse(raw)
        assert "event: task_done" in sse
        assert 'data: {"status": "ok"}' in sse
        assert sse.endswith("\n\n")

    def test_format_sse_invalid_json_fallback(self):
        """format_sse() 对非法 JSON 应降级为 data: 原始文本"""
        sse = format_sse("not json")
        assert sse.startswith("data: not json")

    def test_emit_log_capped(self):
        """emit 的滚动日志不应超过 _MAX_LOG 上限"""
        # 大量 emit 触发裁剪
        for i in range(250):
            emit("bulk", {"i": i})
        # 新订阅者收到的历史应 <= 200
        _, replay = subscribe()
        assert len(replay) <= 200


class TestEventBusEdgeCases:
    """事件总线边界情况测试"""

    def test_emit_empty_data(self):
        """emit() 应能处理空 data"""
        q, _ = subscribe()
        emit("ping", {})
        msg = q.get(timeout=1)
        parsed = json.loads(msg)
        assert parsed["event"] == "ping"
        assert parsed["data"] == {}
        unsubscribe(q)

    def test_subscribe_unsubscribe_no_side_effects(self):
        """多次 subscribe/unsubscribe 不应残留"""
        queues = []
        for _ in range(5):
            q, _ = subscribe()
            queues.append(q)
        for q in queues:
            unsubscribe(q)
        # 再 emit 不应有任何残留
        emit("clean", {})
        for q in queues:
            assert q.empty()
