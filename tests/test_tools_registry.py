"""
test_tools_registry.py — 工具注册表单元测试
"""
import pytest
from references.tools_registry import (
    TOOL_DEFS, TOOL_CATEGORIES, TOOL_USAGE_HINTS,
    get_tools_for_role, get_tool_names_for_role,
    filter_tools_for_task, build_tools_prompt,
    execute_tool,
    _check_dangerous_code, _check_dangerous_bash_code,
)


class TestToolDefinitions:
    """工具定义完整性测试"""

    def test_all_tools_have_defs(self):
        """所有注册的工具都应有定义"""
        defined = set(TOOL_DEFS.keys())
        categorized = set(TOOL_CATEGORIES.keys())
        hinted = set(TOOL_USAGE_HINTS.keys())
        # 这三个集合应一致
        assert defined == categorized, f"定义/分类不一致：{defined ^ categorized}"
        # 提示可以少一些（不是所有工具都需要）
        assert hinted.issubset(defined), f"多余提示：{hinted - defined}"

    def test_each_tool_def_has_required_fields(self):
        """每个工具定义应有 name, description, parameters"""
        for name, defn in TOOL_DEFS.items():
            assert "name" in defn, f"{name} 缺少 name"
            assert "description" in defn, f"{name} 缺少 description"
            assert "parameters" in defn, f"{name} 缺少 parameters"
            assert "required" in defn["parameters"], f"{name} 缺少 parameters.required"

    def test_ui_ux_search_tool_included(self):
        """ui_ux_search 工具应存在于 TOOL_DEFS"""
        assert "ui_ux_search" in TOOL_DEFS
        defn = TOOL_DEFS["ui_ux_search"]
        assert "domain" in defn["parameters"]["properties"]


class TestFilterToolsForTask:
    """Tool Loadout 动态筛选测试"""

    def test_empty_task_returns_all(self):
        """空任务描述应返回全部工具"""
        tools = ["web_search", "code_run", "file_read"]
        result = filter_tools_for_task(tools, "")
        assert result == tools

    def test_search_task_filters_relevant(self):
        """搜索类任务应保留搜索工具"""
        tools = ["web_search", "code_run", "file_read", "bash"]
        result = filter_tools_for_task(tools, "搜索 API 文档和最佳实践")
        assert "web_search" in result

    def test_deploy_task_filters_relevant(self):
        """部署类任务应保留部署工具"""
        tools = ["web_search", "code_run", "bash", "file_write"]
        result = filter_tools_for_task(tools, "部署服务到生产环境")
        assert "bash" in result

    def test_io_tools_always_included(self):
        """IO 类工具（file_read/file_write）应始终保留"""
        tools = ["code_run", "bash", "file_read", "file_write"]
        result = filter_tools_for_task(tools, "运行测试")
        assert "file_read" in result
        assert "file_write" in result

    def test_no_match_returns_all(self):
        """任务无任何匹配关键词时应返回全部"""
        tools = ["web_search", "code_run"]
        result = filter_tools_for_task(tools, "xyz123nonexistentkeyword")
        assert result == tools


class TestGetToolsForRole:
    """角色工具绑定测试"""

    def test_pm_has_core_tools(self):
        """PM 角色应具备核心工具"""
        tools = get_tools_for_role("pm")
        names = [t["name"] for t in tools]
        assert "web_search" in names
        assert "file_read" in names
        assert "file_write" in names

    def test_ux_has_ui_ux_search(self):
        """UX 角色应具备 ui_ux_search 工具"""
        tools = get_tools_for_role("ux")
        names = [t["name"] for t in tools]
        assert "ui_ux_search" in names

    def test_unknown_role_returns_empty(self):
        """未知角色应返回空列表"""
        tools = get_tools_for_role("nonexistent_role")
        assert tools == []

    def test_returns_tool_def_dicts(self):
        """get_tools_for_role 应返回完整的工具定义"""
        tools = get_tools_for_role("frontend")
        assert len(tools) >= 1
        assert "parameters" in tools[0]

    def test_task_context_filters_tools(self):
        """task_context 应动态筛选工具—部署任务应保留 bash"""
        names = get_tool_names_for_role("backend", "部署服务")
        assert "bash" in names  # "部署"/"服务" 属于 bash 触发器
        assert "file_read" in names  # IO 工具始终保留


class TestBuildToolsPrompt:
    """工具使用提示生成测试"""

    def test_build_tools_prompt_not_empty(self):
        """build_tools_prompt() 应返回非空提示"""
        prompt = build_tools_prompt("frontend")
        assert prompt
        assert "可用工具" in prompt

    def test_build_tools_prompt_xml_format(self):
        """默认 XML 格式应包含 invoke 示例"""
        prompt = build_tools_prompt("frontend")
        assert "<invoke" in prompt
        assert "xml" in prompt.lower()

    def test_build_tools_prompt_native_format(self):
        """use_native_format=True 应使用 function calling 提示"""
        prompt = build_tools_prompt("frontend", use_native_format=True)
        assert "function calling" in prompt.lower()

    def test_build_tools_prompt_task_context(self):
        """task_context 应筛选提示中展示的工具"""
        prompt = build_tools_prompt("backend", task_context="部署上线")
        assert "bash" in prompt


class TestExecuteTool:
    """工具执行器测试"""

    def test_execute_unknown_tool(self):
        """未知工具应返回错误信息"""
        result = execute_tool("nonexistent_tool", {})
        assert "未知工具" in result

    def test_execute_tool_with_exception(self):
        """执行异常时应返回友好的错误"""
        result = execute_tool("file_read", {"path": "nonexistent_file_xyz123.txt"})
        assert "文件不存在" in result or "错误" in result

    def test_execute_file_read(self, tmp_path):
        """file_read 应读取文件内容"""
        test_file = tmp_path / "test_hello.txt"
        test_file.write_text("hello world\nline 2\n", encoding="utf-8")
        # file_read 使用 Path 对象，我们需要在临时目录中测试
        result = execute_tool("file_read", {"path": str(test_file)})
        assert "hello world" in result


class TestSecurityCheckers:
    """安全扫描功能测试"""

    def test_check_dangerous_code_detects_os_system(self):
        """应检测 os.system 调用"""
        result = _check_dangerous_code("import os; os.system('rm -rf /')")
        assert result is not None
        assert "危险" in result

    def test_check_dangerous_code_detects_subprocess(self):
        """应检测 subprocess 调用"""
        result = _check_dangerous_code("import subprocess; subprocess.run(['rm'])")
        assert result is not None
        assert "危险" in result

    def test_check_dangerous_code_detects_eval(self):
        """应检测 eval 调用"""
        result = _check_dangerous_code("eval('__import__(\"os\").system(\"ls\")')")
        assert result is not None

    def test_check_dangerous_code_safe_code(self):
        """安全的 Python 代码应通过"""
        result = _check_dangerous_code("print('hello')\nx = 1 + 2")
        assert result is None

    def test_check_dangerous_code_detects_compile(self):
        """应检测 compile() 调用"""
        result = _check_dangerous_code("compile('code', '', 'exec')")
        assert result is not None

    def test_check_dangerous_bash_code_detects_rm_rf(self):
        """应检测 rm -rf 命令"""
        result = _check_dangerous_bash_code("rm -rf /some/dir")
        assert result is not None
        assert "拒绝" in result

    def test_check_dangerous_bash_code_detects_dd(self):
        """应检测 dd 命令"""
        result = _check_dangerous_bash_code("dd if=/dev/zero of=/dev/sda")
        assert result is not None

    def test_check_dangerous_bash_code_safe(self):
        """安全的 bash 命令应通过"""
        result = _check_dangerous_bash_code("ls -la /app")
        assert result is None
        result = _check_dangerous_bash_code("echo hello")
        assert result is None
        result = _check_dangerous_bash_code("pip install requests")
        assert result is None

    def test_check_dangerous_bash_code_detects_systemctl(self):
        """应检测 systemctl 命令"""
        result = _check_dangerous_bash_code("systemctl stop nginx")
        assert result is not None
