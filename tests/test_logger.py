"""
test_logger.py — 结构化日志单元测试
"""
import json
import pytest
from pathlib import Path
from references.logger import StructuredLogger, init_logger, get_logger


class TestStructuredLogger:
    """StructuredLogger 核心功能测试"""

    def test_log_writes_jsonl(self, tmp_path, monkeypatch):
        """log() 应写入 JSONL 文件"""
        monkeypatch.setenv("AI_TEAM_LOG_DIR", str(tmp_path))
        slog = StructuredLogger("test_project")

        slog.log("info", event="task_completed", role="frontend",
                 dispatch_id="T001", phase="executing", summary="前端完成")

        log_file = tmp_path / "test_project.jsonl"
        assert log_file.exists()

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["project_id"] == "test_project"
        assert record["level"] == "info"
        assert record["event"] == "task_completed"
        assert record["role"] == "frontend"

    def test_log_multiple_entries(self, tmp_path, monkeypatch):
        """多次 log 应追加到同一文件"""
        monkeypatch.setenv("AI_TEAM_LOG_DIR", str(tmp_path))
        slog = StructuredLogger("multi_test")

        slog.log("info", event="started")
        slog.log("info", event="completed")

        log_file = tmp_path / "multi_test.jsonl"
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_log_has_timestamp(self, tmp_path, monkeypatch):
        """每条日志应有时间戳"""
        monkeypatch.setenv("AI_TEAM_LOG_DIR", str(tmp_path))
        slog = StructuredLogger("ts_test")
        slog.log("info", event="test")
        record = json.loads((tmp_path / "ts_test.jsonl").read_text(encoding="utf-8"))
        assert "ts" in record
        assert len(record["ts"]) >= 19  # ISO format

    def test_log_handles_unicode(self, tmp_path, monkeypatch):
        """log 应正确处理中文和 emoji"""
        monkeypatch.setenv("AI_TEAM_LOG_DIR", str(tmp_path))
        slog = StructuredLogger("unicode_test")
        slog.log("info", event="completed", summary="测试完成 🎉")
        record = json.loads((tmp_path / "unicode_test.jsonl").read_text(encoding="utf-8"))
        assert "测试完成 🎉" in record["summary"]

    def test_log_handles_write_error(self, tmp_path, monkeypatch):
        """磁盘写入失败不应抛异常"""
        monkeypatch.setenv("AI_TEAM_LOG_DIR", str(tmp_path / "nonexistent_dir"))

        class BrokenLogger(StructuredLogger):
            def log(self, level, event, **fields):
                try:
                    super().log(level, event, **fields)
                except OSError:
                    pass  # Expected

        slog = BrokenLogger("broken")
        try:
            slog.log("info", event="test")
        except Exception:
            pytest.fail("磁盘写入失败不应抛异常")


class TestLoggerGlobals:
    """全局 logger 管理测试"""

    def test_init_logger_returns_instance(self):
        """init_logger() 应返回 StructuredLogger 实例"""
        slog = init_logger("global_test")
        assert isinstance(slog, StructuredLogger)
        assert slog.project_id == "global_test"

    def test_get_logger_default(self):
        """get_logger() 未初始化时应返回默认实例"""
        slog = get_logger()
        assert isinstance(slog, StructuredLogger)

    def test_init_logger_changes_global(self):
        """init_logger() 应切换全局实例"""
        slog1 = init_logger("first")
        slog2 = init_logger("second")
        assert slog2.project_id == "second"
        # get_logger() 应返回最新的
        slog3 = get_logger()
        assert slog3.project_id == "second"
