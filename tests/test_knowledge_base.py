"""
test_knowledge_base.py — 知识库单元测试
"""
import json
import pytest
from pathlib import Path


class TestKnowledgeBaseInit:
    """知识库初始化测试"""

    def test_init_knowledge_base_creates_dirs(self, tmp_path, monkeypatch):
        """init_knowledge_base() 应创建目录结构"""
        import references.knowledge_base as kb
        # 替换模块级路径为 tmp_path
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        # 重新 init
        kb.init_knowledge_base("test_project")

        assert (tmp_path / "knowledge" / "curated" / "standards.md").exists()
        assert (tmp_path / "knowledge" / "curated" / "glossary.md").exists()
        assert (tmp_path / "knowledge" / "curated" / "gotchas.md").exists()
        assert (tmp_path / "knowledge" / "auto" / "decisions.md").exists()
        assert (tmp_path / "knowledge" / "auto" / "gotchas.md").exists()
        assert (tmp_path / "knowledge" / "auto" / "postmortems.md").exists()
        assert (tmp_path / "knowledge" / "auto" / "_manifest.json").exists()

    def test_init_knowledge_base_manifest_content(self, tmp_path, monkeypatch):
        """manifest JSON 应包含项目名和空条目"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("my_project")
        manifest = json.loads((tmp_path / "knowledge" / "auto" / "_manifest.json").read_text(encoding="utf-8"))
        assert manifest["project"] == "my_project"
        assert manifest["entries"] == []

    def test_init_knowledge_base_no_duplicate_defaults(self, tmp_path, monkeypatch):
        """再次 init 不应覆盖已有文件"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("first")
        # 修改一个文件内容
        (tmp_path / "knowledge" / "curated" / "glossary.md").write_text("# 自定义词汇表\n\nfoo\n", encoding="utf-8")
        kb.init_knowledge_base("second")
        # 不应被覆盖
        content = (tmp_path / "knowledge" / "curated" / "glossary.md").read_text(encoding="utf-8")
        assert "foo" in content


class TestKnowledgeBaseRead:
    """知识库读取测试"""

    def test_read_section_curated(self, tmp_path, monkeypatch):
        """read_section() 应读取 curated/ 下的内容"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        content = kb.read_section("standards", "curated")
        assert "编码规范" in content

    def test_read_section_not_found(self, tmp_path, monkeypatch):
        """不存在的章节应返回错误信息"""
        import references.knowledge_base as kb
        content = kb.read_section("nonexistent", "curated")
        assert "未知章节" in content

    def test_build_kb_context_empty_role(self, tmp_path, monkeypatch):
        """未知角色应返回空字符串"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        # 覆盖 ROLE_KB_SECTIONS 去掉 unknown 的映射
        role_sections = dict(kb.ROLE_KB_SECTIONS)
        ctx = kb.build_kb_context("unknown_role")
        assert ctx == ""

    def test_build_kb_context_reviewer(self, tmp_path, monkeypatch):
        """reviewer 角色应只拿到 standards 内容"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        ctx = kb.build_kb_context("reviewer")
        # 应包含 standards 章节标记和具体内容
        assert ctx.startswith("[知识库：standards]")
        assert "所有成员遵守本规范" in ctx


class TestKnowledgeBaseWrite:
    """知识库写入测试"""

    def test_add_glossary_appends_entry(self, tmp_path, monkeypatch):
        """add_glossary() 应追加词汇条目到 glossary.md"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_glossary("REST", "Representational State Transfer", "GET /api/users")
        content = (tmp_path / "knowledge" / "curated" / "glossary.md").read_text(encoding="utf-8")
        assert "**REST**" in content
        assert "Representational State Transfer" in content
        assert "GET /api/users" in content

    def test_add_adr_creates_entry(self, tmp_path, monkeypatch):
        """add_adr() 应追加 ADR 记录到 decisions.md"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_adr("使用 PostgreSQL", "需要关系型数据库", "选 PG 15", "ACID 保障")
        content = (tmp_path / "knowledge" / "auto" / "decisions.md").read_text(encoding="utf-8")
        assert "ADR-001" in content
        assert "使用 PostgreSQL" in content

    def test_add_adr_increments_counter(self, tmp_path, monkeypatch):
        """多次 add_adr 应递增 ADR 编号"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_adr("决策一", "ctx", "dec1", "c1")
        kb.add_adr("决策二", "ctx", "dec2", "c2")
        content = (tmp_path / "knowledge" / "auto" / "decisions.md").read_text(encoding="utf-8")
        assert "ADR-001" in content
        assert "ADR-002" in content

    def test_add_gotcha_creates_entry(self, tmp_path, monkeypatch):
        """add_gotcha() 应追加踩坑记录"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_gotcha("API 超时", "请求卡住", "连接池用完", "增加连接数", ["backend"])
        content = (tmp_path / "knowledge" / "auto" / "gotchas.md").read_text(encoding="utf-8")
        assert "API 超时" in content
        assert "增加连接数" in content

    def test_add_postmortem_creates_entry(self, tmp_path, monkeypatch):
        """add_postmortem() 应追加故障复盘记录"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_postmortem("生产宕机", "14:00 发现", "磁盘满", "服务不可用 30 分钟", ["加监控", "设告警"])
        content = (tmp_path / "knowledge" / "auto" / "postmortems.md").read_text(encoding="utf-8")
        assert "生产宕机" in content
        assert "加监控" in content

    def test_manifest_tracks_auto_entries(self, tmp_path, monkeypatch):
        """auto/ 写入应在 manifest 中留下记录"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_gotcha("测试坑", "xxx", "yyy", "zzz", [])
        manifest = json.loads((tmp_path / "knowledge" / "auto" / "_manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["entries"]) == 1
        assert manifest["entries"][0]["title"] == "测试坑"
        assert manifest["entries"][0]["reviewed"] is False


class TestKnowledgeBaseReview:
    """知识库审查流程测试"""

    def test_list_pending_review(self, tmp_path, monkeypatch):
        """list_pending_review() 应列出未审查条目"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_gotcha("未审查坑", "s", "c", "sol", [])
        pending = kb.list_pending_review()
        assert len(pending) == 1
        assert pending[0]["reviewed"] is False

    def test_promote_to_curated(self, tmp_path, monkeypatch):
        """promote_to_curated() 应将条目从 auto 移到 curated"""
        import references.knowledge_base as kb
        monkeypatch.setattr(kb, "KB_DIR", tmp_path / "knowledge")
        monkeypatch.setattr(kb, "CURATED_DIR", tmp_path / "knowledge" / "curated")
        monkeypatch.setattr(kb, "AUTO_DIR", tmp_path / "knowledge" / "auto")
        monkeypatch.setattr(kb, "MANIFEST_PATH", tmp_path / "knowledge" / "auto" / "_manifest.json")

        kb.init_knowledge_base("test")
        kb.add_gotcha("提升测试", "symptom", "cause", "solution", ["fe"])
        result = kb.promote_to_curated("gotchas.md", "提升测试")
        assert result is True
        # auto 中应移除
        auto_content = (tmp_path / "knowledge" / "auto" / "gotchas.md").read_text(encoding="utf-8")
        assert "提升测试" not in auto_content
        # curated 中应存在（且不含"Agent 生成"标记）
        curated_content = (tmp_path / "knowledge" / "curated" / "gotchas.md").read_text(encoding="utf-8")
        assert "提升测试" in curated_content

    def test_promote_nonexistent_entry(self, tmp_path, monkeypatch):
        """提升不存在的条目应返回 False"""
        import references.knowledge_base as kb
        result = kb.promote_to_curated("gotchas.md", "不存在的条目")
        assert result is False
