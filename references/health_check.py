"""
health_check.py — 启动前健康检查
==================================
server.py 启动时调用 preflight_check()，所有检查通过后才启动。

检查项：
  1. 11 个角色文件齐全
  2. 当前 provider 的 API Key 已配置
  3. knowledge/ 目录结构正确
  4. master.json schema 版本匹配
  5. 端口可用
  6. logs/ 目录可写
  7. Python 依赖已安装
"""

import importlib
import os
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = Path(__file__).resolve().parent


def preflight_check(port: int = 8123) -> bool:
    """
    执行所有启动前检查，返回 True 表示全部通过。
    有失败项时打印详情并返回 False。
    """
    print("=" * 50)
    print("AI Team — 启动健康检查")
    print("=" * 50)
    print()

    checks = [
        ("11 个角色文件齐全",   _check_role_files),
        ("API Key 已配置",       _check_api_key),
        ("knowledge/ 目录结构",   _check_kb_structure),
        ("master.json schema",  _check_schema),
        (f"端口 {port} 可用",    lambda: _check_port(port)),
        ("logs/ 目录可写",       _check_log_writable),
        ("Python 依赖已安装",    _check_dependencies),
    ]

    all_ok = True
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, str(e)

        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}: {msg}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("  [OK] 所有检查通过，服务器启动中...")
    else:
        print("  [FAIL] 启动失败，请修复以上问题后重试。")

    print("=" * 50)
    return all_ok


def _check_role_files():
    """检查角色目录下的 prompt.md 文件是否存在。"""
    from role_registry import get_role_prompt, get_all_roles

    roles = get_all_roles()
    if not roles:
        return False, "未发现任何角色配置（roles/*/config.yaml）"

    missing = []
    for role in roles:
        prompt = get_role_prompt(role)
        if not prompt:
            missing.append(f"{role}/prompt.md")

    if missing:
        return False, f"缺少角色文件：{', '.join(missing)}"
    return True, f"共 {len(roles)} 个角色文件"

def _check_api_key():
    """检查当前 provider 的 API Key 环境变量。"""
    from model_adapter import ACTIVE_PROVIDER

    key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "claude":   "ANTHROPIC_API_KEY",
        "openai":   "OPENAI_API_KEY",
        "gemini":   "GEMINI_API_KEY",
        "any":      "AI_TEAM_API_KEY",
    }

    env_var = key_map.get(ACTIVE_PROVIDER)
    if not env_var:
        return False, f"未知 provider: {ACTIVE_PROVIDER}"

    val = os.environ.get(env_var)
    if not val:
        return False, (
            f"缺少环境变量 {env_var}（当前 provider: {ACTIVE_PROVIDER}）。"
            f"请设置 export {env_var}=\"your-key\""
        )
    return True, f"{env_var} (provider={ACTIVE_PROVIDER})"

def _check_kb_structure():
    """检查 knowledge/curated/ 目录存在且含 manifest。"""
    kb_dir = PROJECT_ROOT / "knowledge"
    curated = kb_dir / "curated"
    if not curated.exists() or not curated.is_dir():
        return False, f"knowledge/curated/ 目录不存在：{curated}"

    manifest = curated / "_manifest.json"
    if not manifest.exists():
        return False, f"manifest 文件不存在：{manifest}"

    # 检查 manifest 是否可读
    import json
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        entries = len(data) if isinstance(data, dict) else len(list(data))
        return True, f"knowledge/curated/ 就绪（{entries} 条记录）"
    except json.JSONDecodeError:
        return False, f"manifest 文件 JSON 损坏：{manifest}"
    except Exception as e:
        return False, str(e)

def _check_schema():
    """检查 master.json schema 版本。"""
    master = PROJECT_ROOT / "state" / "master.json"
    if not master.exists():
        return True, "master.json 尚未创建（首次运行会自动创建）"

    import json
    try:
        data = json.loads(master.read_text(encoding="utf-8"))
        v = data.get("_meta", {}).get("schema_version", "unknown")
        if v == "2.0":
            return True, f"v{v}"
        else:
            return False, f"schema 版本不匹配：期望 2.0，实际 {v}"
    except json.JSONDecodeError:
        return False, "master.json JSON 格式损坏"

def _check_port(port: int):
    """检查端口是否可绑定。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True, f"端口 {port} 可用"
    except OSError:
        s.close()
        return False, f"端口 {port} 已被占用"
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        return False, str(e)

def _check_log_writable():
    """检查 logs/ 目录是否可写（不存在则创建）。"""
    logs_dir = PROJECT_ROOT / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        test_file = logs_dir / ".test_write"
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True, f"logs/ 可写 ({logs_dir})"
    except OSError as e:
        return False, f"logs/ 不可写：{e}"
    except Exception as e:
        return False, str(e)

def _check_dependencies():
    """检查 requirements.txt 中的关键依赖是否可导入。"""
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        return True, "requirements.txt 不存在，跳过检查"

    import_map = {
        "anthropic":  "anthropic",
        "openai":     "openai",
        "google-genai": "google.generativeai",
        "pyyaml":     "yaml",
    }

    missing = []
    for pkg_name, import_name in import_map.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        return False, f"缺少依赖：{', '.join(missing)}。请运行 pip install -r requirements.txt"
    return True, "核心依赖已安装"
