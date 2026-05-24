"""
test_circuit_breaker.py — 熔断器单元测试
"""
import time
import json
import pytest
from pathlib import Path
from references.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """熔断器核心功能测试"""

    def test_initially_closed(self, tmp_path):
        """新建熔断器应为关闭状态"""
        cb = CircuitBreaker(max_failures=3, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        assert not cb.is_open()

    def test_open_after_threshold(self, tmp_path):
        """超过阈值后熔断器应打开"""
        cb = CircuitBreaker(max_failures=3, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        for i in range(3):
            cb.record_failure("test_role", f"error {i}")
        assert cb.is_open()

    def test_not_open_below_threshold(self, tmp_path):
        """低于阈值时熔断器不应打开"""
        cb = CircuitBreaker(max_failures=5, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        for i in range(3):
            cb.record_failure("test_role", f"error {i}")
        assert not cb.is_open()

    def test_record_success_clears_failures(self, tmp_path):
        """record_success() 应清空指定角色的失败记录"""
        cb = CircuitBreaker(max_failures=3, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("role_a", "err1")
        cb.record_failure("role_a", "err2")
        cb.record_success("role_a")
        # 再记录一次应不触发熔断
        cb.record_failure("role_a", "err3")
        assert not cb.is_open()

    def test_record_success_clears_all_without_role(self, tmp_path):
        """record_success('') 应清空内存中所有角色的记录（不删 flag 文件，需 reset() 恢复）"""
        cb = CircuitBreaker(max_failures=2, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("role_a", "err1")
        cb.record_failure("role_b", "err2")
        cb.record_success("")  # 无指定角色，清空 deque
        # record_success 只清内存计数器，不删 flag 文件
        # 用 reset() 可彻底恢复
        cb.reset()
        assert not cb.is_open()

    def test_reset_closes_breaker(self, tmp_path):
        """reset() 应关闭熔断器并删除标志文件"""
        cb = CircuitBreaker(max_failures=2, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("r", "e1")
        cb.record_failure("r", "e2")
        assert cb.is_open()
        cb.reset()
        assert not cb.is_open()
        assert not cb.flag_file.exists()

    def test_reason_returns_empty_when_closed(self, tmp_path):
        """熔断器关闭时 reason() 应返回空字符串"""
        cb = CircuitBreaker()
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        assert cb.reason() == ""

    def test_reason_returns_description_when_open(self, tmp_path):
        """熔断器打开时 reason() 应返回描述信息（last_error 是最近一次错误）"""
        cb = CircuitBreaker(max_failures=2, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("test_role", "connection refused")
        cb.record_failure("test_role", "timeout")
        reason = cb.reason()
        assert "熔断器" in reason
        assert "test_role" in reason
        # last_error 为最近一次错误
        assert "timeout" in reason

    def test_auto_clear_after_timeout(self, tmp_path):
        """超过 30 分钟后熔断器应自动清除"""
        cb = CircuitBreaker(max_failures=2, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("r", "e1")
        cb.record_failure("r", "e2")
        # 手动修改 flag 文件的时间戳为 31 分钟前
        assert cb.flag_file.exists()
        data = json.loads(cb.flag_file.read_text(encoding="utf-8"))
        import datetime
        old_time = (datetime.datetime.now() - datetime.timedelta(minutes=31)).isoformat()
        data["opened_at"] = old_time
        cb.flag_file.write_text(json.dumps(data), encoding="utf-8")
        # is_open 应返回 False（自动清除）
        assert not cb.is_open()
        assert not cb.flag_file.exists()


class TestCircuitBreakerEdgeCases:
    """熔断器边界情况测试"""

    def test_flag_file_corrupted(self, tmp_path):
        """标志文件损坏时应 graceful 处理"""
        cb = CircuitBreaker(max_failures=2, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.flag_file.write_text("not valid json", encoding="utf-8")
        # 不应抛异常
        assert cb.is_open()  # 文件存在就算打开

    def test_window_expiry_clears_old_failures(self, tmp_path):
        """窗口外的旧失败记录应自动清除"""
        cb = CircuitBreaker(max_failures=3, window_seconds=1)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        cb.record_failure("r", "old")
        time.sleep(1.5)
        cb.record_failure("r", "new1")
        cb.record_failure("r", "new2")
        # 此时窗口内只有 2 条（old 已过期）
        assert not cb.is_open()

    def test_write_flag_permission_error(self, tmp_path, mocker):
        """写入标志文件失败不应抛异常"""
        import os
        cb = CircuitBreaker(max_failures=1, window_seconds=60)
        cb.flag_file = tmp_path / "CIRCUIT_OPEN.flag"
        # 使用 mocker 替换 _write_flag 方法，模拟写入失败
        original_write_flag = cb._write_flag
        def broken_write_flag(trigger_role, last_error):
            raise PermissionError("access denied")
        mocker.patch.object(cb, '_write_flag', side_effect=PermissionError("access denied"))
        try:
            cb.record_failure("r", "e")
        except PermissionError:
            pytest.fail("_write_flag 失败不应传播到 record_failure")
        # 同时验证无 mocker 时正常工作的路径
        cb2 = CircuitBreaker(max_failures=1, window_seconds=60)
        cb2.flag_file = tmp_path / "CIRCUIT_OPEN2.flag"
        cb2.record_failure("r", "e")
        assert cb2.is_open()
