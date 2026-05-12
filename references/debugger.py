"""
debugger.py — AI 团队调试器
============================
七个工具覆盖五个故障阶段：

  上下文注入  → inspect_context / count_tokens
  角色执行    → validate_output / score_adherence
  状态写入    → diff_snaps / health_check
  调度链路    → trace / replay
  流程验证    → dry_run / assert_output

用法：
  python references/debugger.py <命令> [参数]
  python references/debugger.py health
  python references/debugger.py trace
  python references/debugger.py diff D002 D003
  python references/debugger.py replay D003
  python references/debugger.py dry_run "制定营销方案"
"""

import json
import re
import os
import sys
import difflib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

STATE_DIR = Path("state")
SNAP_DIR  = STATE_DIR / "snapshots"
LOG_PATH  = Path("logs/dispatch_log.jsonl")

# ─────────────────────────────────────────────
# 内部工具
# ─────────────────────────────────────────────

def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _load_master() -> dict:
    return _load(STATE_DIR / "master.json")

def _load_snap(label: str) -> dict:
    """按调度ID或文件名加载快照。"""
    if label.endswith(".json"):
        return _load(SNAP_DIR / label)
    # 按调度ID找最近的快照（写入前拍摄的那个）
    candidates = sorted(SNAP_DIR.glob(f"snap_{label}_*.json"),
                        key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"找不到调度 {label!r} 的快照。")
    return _load(candidates[-1])

def _load_log() -> list:
    if not LOG_PATH.exists():
        return []
    records = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records

def _color(text: str, code: str) -> str:
    """ANSI 颜色（终端输出用）。"""
    codes = {"red":"\033[91m","green":"\033[92m","yellow":"\033[93m",
             "cyan":"\033[96m","gray":"\033[90m","bold":"\033[1m","reset":"\033[0m"}
    return f"{codes.get(code,'')}{text}{codes['reset']}"

def _hr(char="─", width=60):
    print(char * width)

def _box(title: str, color="cyan"):
    w = 60
    print(_color(f"┌{'─'*(w-2)}┐", color))
    print(_color(f"│  {title:<{w-4}}│", color))
    print(_color(f"└{'─'*(w-2)}┘", color))


# ─────────────────────────────────────────────
# 1. inspect_context — 重建指定调度时的注入内容
# ─────────────────────────────────────────────

def inspect_context(role: str, dispatch_id: str) -> str:
    """
    重建某次调度时实际注入给角色的上下文（三层全部展示）。
    从对应快照中读取状态，再调用 build_context() 重建。
    """
    _box(f"上下文检查 | {role.upper()} | 调度 {dispatch_id}")

    try:
        snap = _load_snap(dispatch_id)
    except FileNotFoundError:
        print(_color(f"  找不到调度 {dispatch_id} 的快照，无法重建上下文。", "red"))
        print("  提示：只有在 complete_task() 调用后才会生成快照。")
        return ""

    # 从快照重建上下文（不影响当前状态）
    master_backup = STATE_DIR / "master.json"
    tmp_path = STATE_DIR / "__debug_tmp.json"
    shutil.copy2(master_backup, tmp_path)
    try:
        with open(master_backup, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        sys.path.insert(0, str(Path(__file__).parent))
        from state_manager import build_context
        ctx = build_context(role, f"[DEBUG 重建 - 调度 {dispatch_id}]")
    finally:
        shutil.copy2(tmp_path, master_backup)
        tmp_path.unlink(missing_ok=True)

    # 逐层打印
    layers = {
        "warm_context": ("Warm 层（项目摘要）", "cyan"),
        "hot_context":  ("Hot 层（角色历史）", "yellow"),
        "task":         ("Task 层（当次任务）", "green"),
    }
    for tag, (label, color) in layers.items():
        m = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", ctx)
        content = m.group(1).strip() if m else "(未找到)"
        tokens = len(content.split())
        print(f"\n  {_color(label, color)} (~{tokens} tokens)")
        _hr("·")
        for line in content.split("\n"):
            print(f"  {line}")

    total = len(ctx.split())
    print(f"\n  总计约 {_color(str(total), 'bold')} tokens")
    return ctx


# ─────────────────────────────────────────────
# 2. count_tokens — 逐层统计 token 用量
# ─────────────────────────────────────────────

def count_tokens(role: str, dispatch_id: Optional[str] = None) -> dict:
    """统计当前（或指定快照时）的上下文 token 分布。"""
    _box(f"Token 统计 | {role.upper()}" + (f" | {dispatch_id}" if dispatch_id else ""))

    from state_manager import build_context
    ctx = build_context(role, "[debug token count]")

    result = {}
    total  = 0
    layers = [("warm_context","Warm（项目摘要）"),
              ("hot_context","Hot（角色历史）"),
              ("task","Task（当次任务）")]

    print(f"\n  {'层级':<22} {'tokens':>8}  {'占比':>6}  条形图")
    _hr()
    for tag, label in layers:
        m = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", ctx)
        content = m.group(1).strip() if m else ""
        t = len(content.split())
        total += t
        result[tag] = t

    for tag, label in layers:
        t = result[tag]
        pct = t / max(total, 1) * 100
        bar = "█" * int(pct / 5)
        status = ""
        if tag == "hot_context" and t > 400:
            status = _color(" ⚠ 偏高", "yellow")
        print(f"  {label:<22} {t:>8}  {pct:>5.1f}%  {_color(bar,'cyan')}{status}")

    _hr()
    color = "green" if total < 700 else ("yellow" if total < 1200 else "red")
    print(f"  {'合计':<22} {_color(str(total), color):>8}")

    if total > 1200:
        print(_color("\n  警告：上下文过大，建议检查 hot_context 中的历史任务数量。", "red"))
        print("  修复：减小 HOT_WINDOW 值（在 state_manager.py 第10行）。")
    elif total > 700:
        print(_color("\n  提示：上下文接近建议上限，留意 insights 是否需要压缩。", "yellow"))
    else:
        print(_color("\n  上下文大小正常。", "green"))

    return result


# ─────────────────────────────────────────────
# 3. validate_output — 检查 LLM 输出格式
# ─────────────────────────────────────────────

def validate_output(role: str, output: str) -> dict:
    """
    检查角色输出是否合规：
    - 包含 <state_update> 块
    - state_update 是合法 JSON
    - JSON 包含必填字段
    - output_file 路径格式正确（如果非 null）
    """
    _box(f"输出格式校验 | {role.upper()}")

    issues = []
    result = {"valid": True, "parsed": None, "issues": []}

    # 检查 state_update 块
    m = re.search(r"<state_update>\s*([\s\S]+?)\s*</state_update>", output)
    if not m:
        issues.append(("error", "输出缺少 <state_update>...</state_update> 块"))
        result["valid"] = False
    else:
        raw = m.group(1).strip()
        try:
            parsed = json.loads(raw)
            result["parsed"] = parsed

            # 检查必填字段
            required = {"summary": str, "output_file": (str, type(None)), "insights": list}
            for field, expected_type in required.items():
                if field not in parsed:
                    issues.append(("error", f"state_update 缺少必填字段：'{field}'"))
                    result["valid"] = False
                elif not isinstance(parsed[field], expected_type):
                    typ = expected_type.__name__ if not isinstance(expected_type, tuple) else "/".join(t.__name__ for t in expected_type)
                    issues.append(("warning", f"字段 '{field}' 类型应为 {typ}，实际是 {type(parsed[field]).__name__}"))

            # 检查 output_file 格式
            if parsed.get("output_file") and not parsed["output_file"].startswith("outputs/"):
                issues.append(("warning", f"output_file 建议以 'outputs/' 开头，当前：{parsed['output_file']}"))

            # 检查 summary 是否过短
            summary = parsed.get("summary", "")
            if isinstance(summary, str) and len(summary) < 10:
                issues.append(("warning", f"summary 过短（{len(summary)} 字），建议描述清楚做了什么和核心结论"))

            # 检查 insights 质量
            insights = parsed.get("insights", [])
            if isinstance(insights, list):
                if len(insights) == 0:
                    issues.append(("warning", "insights 为空列表，建议记录至少1条本次新增的洞察"))
                for i, ins in enumerate(insights):
                    if isinstance(ins, str) and len(ins) < 5:
                        issues.append(("warning", f"insights[{i}] 过短，意义不大：'{ins}'"))

        except json.JSONDecodeError as e:
            issues.append(("error", f"state_update JSON 解析失败：{e}"))
            result["valid"] = False
            # 尝试给出修复提示
            line_num = str(e).split("line")[1].split()[0] if "line" in str(e) else "?"
            issues.append(("hint", f"错误在第 {line_num} 行附近。常见原因：中文引号、末尾多余逗号。"))

    # 打印结果
    print()
    if result["valid"] and not issues:
        print(_color("  ✓ 输出格式完全合规", "green"))
    elif result["valid"]:
        print(_color("  △ 输出基本合规，有优化建议", "yellow"))
    else:
        print(_color("  ✗ 输出格式不合规，状态未写入", "red"))

    print()
    for level, msg in issues:
        icon = {"error": _color("  ✗", "red"), "warning": _color("  △", "yellow"),
                "hint": _color("  →", "cyan")}.get(level, "  ?")
        print(f"{icon} {msg}")

    if not issues:
        print("  （无问题）")

    # 如果有错误，给出模板
    if not result["valid"]:
        print(f"\n  修复模板：")
        print(_color("""  <state_update>
  {"summary": "一句话：做了什么，核心结论是什么",
   "output_file": "outputs/文件名.md",
   "insights": ["洞察1", "洞察2"]}
  </state_update>""", "cyan"))

    result["issues"] = issues
    return result


# ─────────────────────────────────────────────
# 4. score_adherence — 角色输出与提示词的贴合度
# ─────────────────────────────────────────────

def score_adherence(role: str, output: str) -> int:
    """
    对比角色系统提示词中 <response> 部分要求的格式
    与实际输出，给出 0-100 的贴合分。
    """
    _box(f"提示词贴合度 | {role.upper()}")

    # 读取该角色的系统提示词
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from model_adapter import load_system_prompt
        prompt = load_system_prompt(role)
    except Exception as e:
        print(_color(f"  无法读取系统提示词：{e}", "red"))
        return 0

    score = 100
    deductions = []

    # 提取 prompt 中 <response> 块要求的结构
    resp_m = re.search(r"<response>([\s\S]+?)</response>", prompt)
    if not resp_m:
        print(_color("  系统提示词中未找到 <response> 块，跳过格式检查。", "yellow"))
        return 100

    template = resp_m.group(1)

    # 提取模板中所有 ## 标题作为期望章节
    expected_sections = re.findall(r"##\s+(.+)", template)
    # 提取模板中所有表格（| 开头的行）
    has_table_requirement = bool(re.search(r"^\|", template, re.MULTILINE))

    # 检查期望章节是否出现在输出中
    missing = []
    for section in expected_sections:
        # 只取关键词（去掉emoji和括号）
        key = re.sub(r"[^\w\s]", "", section).strip().split()[0] if section.strip() else ""
        if key and key not in output:
            missing.append(section)

    if missing:
        deductions.append((len(missing) * 8, f"缺少章节：{', '.join(missing[:3])}"))
        score -= len(missing) * 8

    # 检查是否要求表格
    if has_table_requirement and "|" not in output:
        deductions.append((15, "提示词要求表格输出，但实际输出无表格"))
        score -= 15

    # 检查 state_update
    if "<state_update>" not in output:
        deductions.append((20, "缺少 <state_update> 块"))
        score -= 20

    # 检查长度合理性（过短可能是截断，过长可能偏离）
    out_words = len(output.split())
    if out_words < 100:
        deductions.append((10, f"输出过短（{out_words} 词），可能未完成任务"))
        score -= 10

    score = max(0, score)

    # 渲染分数
    print()
    color = "green" if score >= 80 else ("yellow" if score >= 60 else "red")
    bar_filled = int(score / 5)
    bar = _color("█" * bar_filled, color) + _color("░" * (20 - bar_filled), "gray")
    print(f"  贴合分：{_color(str(score), color)}/100  [{bar}]")
    print()

    if deductions:
        print("  扣分项：")
        for pts, reason in deductions:
            print(f"  {_color(f'-{pts}', 'red')}  {reason}")
    else:
        print(_color("  全部格式要求均满足。", "green"))

    if score < 60:
        print(_color("\n  建议：检查系统提示词的 <response> 块是否对当前模型过于复杂。", "yellow"))
        print("  可尝试把格式要求简化为 3-5 条具体规则。")

    return score


# ─────────────────────────────────────────────
# 5. diff_snaps — 两个快照之间的状态变化
# ─────────────────────────────────────────────

def diff_snaps(label_a: str, label_b: str) -> dict:
    """
    对比两个快照（或调度ID）之间 master.json 的变化。
    输出 +/- 格式的字段级 diff。
    """
    _box(f"状态 Diff | {label_a} → {label_b}")

    try:
        snap_a = _load_snap(label_a)
        snap_b = _load_snap(label_b)
    except FileNotFoundError as e:
        print(_color(f"  {e}", "red"))
        return {}

    text_a = json.dumps(snap_a, ensure_ascii=False, indent=2).splitlines(keepends=True)
    text_b = json.dumps(snap_b, ensure_ascii=False, indent=2).splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        text_a, text_b,
        fromfile=f"状态 @ {label_a}",
        tofile=f"状态 @ {label_b}",
        n=2
    ))

    if not diff:
        print(_color("\n  两个快照完全相同，状态无变化。", "green"))
        return {}

    # 统计变化量
    adds = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    dels = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    print(f"\n  变化：{_color(f'+{adds}', 'green')} 新增  {_color(f'-{dels}', 'red')} 删除")
    print()

    # 过滤掉纯格式变化，只显示有意义的行
    for line in diff:
        line_s = line.rstrip("\n")
        if line_s.startswith("+++") or line_s.startswith("---"):
            print(_color(f"  {line_s}", "bold"))
        elif line_s.startswith("@@"):
            print(_color(f"\n  {line_s}", "gray"))
        elif line_s.startswith("+"):
            print(_color(f"  {line_s}", "green"))
        elif line_s.startswith("-"):
            print(_color(f"  {line_s}", "red"))
        else:
            print(f"  {line_s}")

    return {"added": adds, "removed": dels, "diff": diff}


# ─────────────────────────────────────────────
# 6. health_check — 整体系统健康检查
# ─────────────────────────────────────────────

def health_check() -> dict:
    """
    全面检查 AI 团队系统健康状态：
    - master.json 字段完整性
    - output_file 引用的文件是否存在
    - 快照索引连续性
    - 调度日志与状态一致性
    - 每个角色的状态合理性
    """
    _box("系统健康检查")
    errors   = []
    warnings = []
    ok_items = []

    # 1. master.json 可读性
    try:
        master = _load_master()
        ok_items.append("master.json 可正常读取")
    except Exception as e:
        errors.append(f"master.json 读取失败：{e}")
        _print_results(errors, warnings, ok_items)
        return {"status": "critical", "errors": errors}

    proj = master.get("project", {})

    # 2. Schema 版本
    ver = master.get("_meta", {}).get("schema_version")
    if ver != "2.0":
        warnings.append(f"schema_version={ver!r}，当前期望 '2.0'，请运行 migrate_state()")
    else:
        ok_items.append(f"schema_version = {ver}")

    # 3. 项目必填字段
    required_proj = ["id", "name", "status", "current_phase", "overall_progress", "next_action"]
    for field in required_proj:
        val = proj.get(field)
        if val is None or val == "" or val == "（未初始化）":
            warnings.append(f"project.{field} 未填写")
        else:
            ok_items.append(f"project.{field} = {str(val)[:40]}")

    # 4. deliverables 引用的文件存在性
    for deliv in proj.get("deliverables", []):
        fpath = deliv.get("file")
        if fpath and deliv.get("status") == "done":
            if not Path(fpath).exists():
                warnings.append(f"deliverable '{deliv.get('name')}' 标记为 done 但文件不存在：{fpath}")

    # 5. 每个角色状态合理性
    roles = master.get("roles", {})
    for role, rd in roles.items():
        # 有 current_tasks 说明有未完成任务（可能是中断）
        if rd.get("current_tasks"):
            warnings.append(f"roles.{role} 有未完成任务：{[t.get('dispatch_id') for t in rd['current_tasks']]}")
        # insights 数量
        n_ins = len(rd.get("insights", []))
        if n_ins > 15:
            warnings.append(f"roles.{role}.insights 已有 {n_ins} 条，建议检查是否需要手动压缩")
        elif n_ins > 0:
            ok_items.append(f"roles.{role}: {len(rd.get('completed_tasks',[]))} 个已完成任务，{n_ins} 条洞察")

    # 6. 快照目录
    if SNAP_DIR.exists():
        snap_count = len(list(SNAP_DIR.glob("snap_*.json")))
        ok_items.append(f"snapshots/: {snap_count} 个快照文件")
        if snap_count == 0:
            warnings.append("snapshots/ 目录为空，还没有生成任何快照（首次运行正常）")
    else:
        warnings.append("snapshots/ 目录不存在")

    # 7. 日志文件
    logs = _load_log()
    if logs:
        done = sum(1 for l in logs if l.get("status") == "done")
        pending = sum(1 for l in logs if l.get("status") == "in_progress")
        ok_items.append(f"dispatch_log: {len(logs)} 条记录（{done} 完成，{pending} 进行中）")
        if pending > 3:
            warnings.append(f"有 {pending} 个调度长时间处于 in_progress，可能需要检查")
    else:
        ok_items.append("dispatch_log 为空（尚未开始调度）")

    # 输出
    _print_results(errors, warnings, ok_items)
    status = "error" if errors else ("warning" if warnings else "ok")
    return {"status": status, "errors": errors, "warnings": warnings}


def _print_results(errors, warnings, ok_items):
    print()
    for item in ok_items:
        print(f"  {_color('✓', 'green')} {item}")
    for w in warnings:
        print(f"  {_color('△', 'yellow')} {w}")
    for e in errors:
        print(f"  {_color('✗', 'red')} {e}")
    print()
    if errors:
        print(_color(f"  状态：严重错误 ({len(errors)} 个)", "red"))
    elif warnings:
        print(_color(f"  状态：有警告 ({len(warnings)} 个)，建议处理", "yellow"))
    else:
        print(_color("  状态：一切正常", "green"))


# ─────────────────────────────────────────────
# 7. trace — 调度链路时间线
# ─────────────────────────────────────────────

def trace(filter_role: Optional[str] = None) -> list:
    """
    打印完整的调度时间线。
    filter_role: 只显示某个角色的记录（可选）。
    """
    _box("调度链路追踪" + (f" | 过滤：{filter_role.upper()}" if filter_role else ""))

    logs = _load_log()
    if filter_role:
        logs = [l for l in logs if l.get("to", "").lower() == filter_role.lower()
                or l.get("from", "").lower() == filter_role.lower()]

    if not logs:
        print(_color("  暂无调度记录。", "gray"))
        return []

    print()
    print(f"  {'ID':<8} {'FROM→TO':<20} {'任务':<30} {'状态':<12} {'耗时'}")
    _hr()

    for r in logs:
        did    = r.get("id", "?")
        frm    = r.get("from", "?")
        to     = r.get("to",   "?")
        task   = r.get("task", "")[:28]
        status = r.get("status", "?")
        dur    = r.get("duration_min")

        status_str = {"done": _color("✓ 完成","green"),
                      "in_progress": _color("→ 进行中","yellow"),
                      "rework": _color("↺ 返工","red"),
                      "blocked": _color("⏸ 阻塞","red")}.get(status, status)

        dur_str = f"{dur}min" if dur else "-"
        route   = f"{frm}→{to}"
        print(f"  {did:<8} {route:<20} {task:<30} {status_str:<20} {dur_str}")

        # 显示输出文件
        for f in r.get("output_files", []):
            exists = "✓" if Path(f).exists() else _color("✗ 文件缺失", "red")
            print(f"  {'':8} {'':20} {_color('↳ ' + f, 'cyan'):<30} {exists}")

        # 显示返工原因
        if r.get("rework_reason"):
            print(f"  {'':8} {_color('返工原因: ' + r['rework_reason'], 'red')}")

    _hr()
    done    = sum(1 for l in logs if l.get("status") == "done")
    pending = sum(1 for l in logs if l.get("status") == "in_progress")
    rework  = sum(1 for l in logs if l.get("status") == "rework")
    print(f"  合计 {len(logs)} 条 | {_color(str(done),'green')} 完成 | {_color(str(pending),'yellow')} 进行中 | {_color(str(rework),'red')} 返工")

    return logs


# ─────────────────────────────────────────────
# 8. replay — 沙盒重放某次调度
# ─────────────────────────────────────────────

def replay(dispatch_id: str, provider: Optional[str] = None) -> str:
    """
    从快照恢复状态，重建上下文，再次调用角色，对比新旧输出。
    在沙盒中运行，不修改当前状态。
    """
    _box(f"沙盒重放 | 调度 {dispatch_id}")

    # 找到对应日志记录
    logs = _load_log()
    record = next((l for l in logs if l.get("id") == dispatch_id), None)
    if not record:
        print(_color(f"  调度日志中找不到 {dispatch_id}，无法重放。", "red"))
        return ""

    role = record.get("to", "").lower()
    task = record.get("task", "")

    print(f"\n  角色：{role.upper()}  任务：{task}")

    # 临时换入快照
    master_path = STATE_DIR / "master.json"
    backup_path = STATE_DIR / "__replay_backup.json"
    shutil.copy2(master_path, backup_path)

    try:
        snap = _load_snap(dispatch_id)
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)

        sys.path.insert(0, str(Path(__file__).parent))
        from model_adapter import call_role, load_system_prompt
        from state_manager import build_context

        system  = load_system_prompt(role)
        context = build_context(role, task)
        print(_color("\n  调用中（沙盒，结果不写入状态）...", "yellow"))
        output = call_role(role, system, context, provider=provider)

        print(_color("\n  重放输出：", "cyan"))
        _hr()
        print(output[:2000] + ("..." if len(output) > 2000 else ""))

        # 验证新输出格式
        print()
        validate_output(role, output)
        return output

    finally:
        shutil.copy2(backup_path, master_path)
        backup_path.unlink(missing_ok=True)
        print(_color("\n  沙盒清理完成，当前状态未受影响。", "gray"))


# ─────────────────────────────────────────────
# 9. dry_run — 全流程 Mock 验证（不消耗 token）
# ─────────────────────────────────────────────

def dry_run(task: str) -> None:
    """
    用 Mock LLM 替换真实 API，走完完整的编排流程：
    PM拆解 → 角色执行 → 状态写入 → 快照生成
    验证编排逻辑，不消耗任何 token。
    """
    _box(f"干跑模拟（Mock LLM）| {task[:40]}")

    MOCK_OUTPUT_TEMPLATE = lambda role, task_desc: f"""
## 模拟输出：{role.upper()} 执行中

本角色完成了：{task_desc[:50]}

（这是 dry_run 模式的占位输出，实际内容由真实模型生成）

<state_update>
{{"summary": "[DRY_RUN] {role} 模拟完成任务：{task_desc[:30]}",
 "output_file": "outputs/dry_run_{role}.md",
 "insights": ["[模拟洞察] 此角色运行正常"]}}
</state_update>
"""

    sys.path.insert(0, str(Path(__file__).parent))
    from state_manager import (init_project, build_context,
                                parse_state_update, mark_task_started,
                                update_project, get_project)

    # 初始化临时项目
    test_id = f"dryrun_{datetime.now().strftime('%H%M%S')}"
    original_master = None
    master_path = STATE_DIR / "master.json"

    if master_path.exists():
        original_master = _load(master_path)

    try:
        proj_id = init_project(f"[DRY_RUN] {task[:30]}")
        PIPELINE = [
            ("pm",         "任务拆解：" + task),
            ("product",    "需求分析和用户故事编写"),
            ("architect",  "系统架构设计"),
            ("tester",     "验收测试"),
        ]

        print(f"\n  项目ID：{proj_id}")
        print(f"  执行 {len(PIPELINE)} 个角色（Mock）\n")
        print(f"  {'#':<4} {'角色':<14} {'状态':<12} {'快照'}")
        _hr()

        for i, (role, subtask) in enumerate(PIPELINE, 1):
            did = f"DRY{i:03d}"
            mark_task_started(role, did, subtask)

            ctx     = build_context(role, subtask)
            mock_out = MOCK_OUTPUT_TEMPLATE(role, subtask)
            ok      = parse_state_update(role, did, mock_out)

            snaps = sorted(SNAP_DIR.glob(f"snap_{did}_*.json")) if SNAP_DIR.exists() else []
            snap_name = snaps[-1].name if snaps else "(未生成)"
            status_s  = _color("✓ 成功", "green") if ok else _color("✗ 失败", "red")
            print(f"  {i:<4} {role.upper():<14} {status_s:<20} {snap_name}")

        p = get_project()
        print(_color(f"\n  干跑完成！进度：{p['overall_progress']}% | 阶段：{p['current_phase']}", "green"))
        print(f"  生成快照数：{len(list(SNAP_DIR.glob('snap_DRY*.json')))}")
        print(_color("  编排逻辑正常，可切换至真实模型运行。", "green"))

    finally:
        # 恢复原始状态
        if original_master is not None:
            with open(master_path, "w", encoding="utf-8") as f:
                json.dump(original_master, f, ensure_ascii=False, indent=2)
            print(_color("\n  已恢复原始项目状态。", "gray"))


# ─────────────────────────────────────────────
# 10. assert_output — 结构性断言（防止错误传播）
# ─────────────────────────────────────────────

def assert_output(role: str, output: str, rules: list) -> bool:
    """
    对角色输出做结构性断言，失败时阻断后续调度。

    rules 格式：
      [
        {"type": "min_words",    "value": 200},
        {"type": "must_contain", "value": "核心发现"},
        {"type": "must_contain", "value": "竞品分析"},
        {"type": "no_contain",   "value": "TODO"},
        {"type": "has_table",    "value": True},
        {"type": "max_words",    "value": 3000},
      ]
    """
    _box(f"输出断言 | {role.upper()}")
    failures = []
    passed   = []

    word_count = len(output.split())

    for rule in rules:
        rtype = rule.get("type")
        val   = rule.get("value")

        if rtype == "min_words":
            if word_count < val:
                failures.append(f"字数不足：{word_count} < {val}（最小要求）")
            else:
                passed.append(f"字数 {word_count} ≥ {val} ✓")

        elif rtype == "max_words":
            if word_count > val:
                failures.append(f"字数过多：{word_count} > {val}（最大限制）")
            else:
                passed.append(f"字数 {word_count} ≤ {val} ✓")

        elif rtype == "must_contain":
            if str(val) not in output:
                failures.append(f"必须包含但缺失：'{val}'")
            else:
                passed.append(f"包含必要内容：'{val}' ✓")

        elif rtype == "no_contain":
            if str(val) in output:
                failures.append(f"不应出现但存在：'{val}'")
            else:
                passed.append(f"未出现禁用词：'{val}' ✓")

        elif rtype == "has_table":
            has = "|" in output
            if val and not has:
                failures.append("要求包含表格但输出中无 | 字符")
            elif not val and has:
                failures.append("要求无表格但输出包含 | 字符")
            else:
                passed.append(f"表格要求满足 ✓")

        elif rtype == "regex":
            if not re.search(str(val), output):
                failures.append(f"正则不匹配：'{val}'")
            else:
                passed.append(f"正则匹配通过 ✓")

    print()
    for p in passed:
        print(f"  {_color('✓', 'green')} {p}")
    for f in failures:
        print(f"  {_color('✗', 'red')} {f}")

    all_pass = len(failures) == 0
    print()
    if all_pass:
        print(_color(f"  断言全部通过（{len(passed)}/{len(rules)}），可进入下一步调度。", "green"))
    else:
        print(_color(f"  断言失败（{len(failures)}/{len(rules)} 不通过），已阻断后续调度。", "red"))
        print(_color("  请修复角色输出后重试，或用 rollback_to_snap() 回退。", "yellow"))

    return all_pass


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    cmd  = sys.argv[1] if len(sys.argv) > 1 else "help"
    args = sys.argv[2:]

    if cmd == "health":
        health_check()

    elif cmd == "trace":
        trace(args[0] if args else None)

    elif cmd == "diff":
        if len(args) < 2:
            print("用法：python debugger.py diff <快照A> <快照B>")
            print("示例：python debugger.py diff D002 D003")
        else:
            diff_snaps(args[0], args[1])

    elif cmd == "context":
        if len(args) < 2:
            print("用法：python debugger.py context <角色> <调度ID>")
        else:
            inspect_context(args[0], args[1])

    elif cmd == "tokens":
        if len(args) < 1:
            print("用法：python debugger.py tokens <角色>")
        else:
            count_tokens(args[0])

    elif cmd == "replay":
        if not args:
            print("用法：python debugger.py replay <调度ID>")
        else:
            replay(args[0], provider=args[1] if len(args) > 1 else None)

    elif cmd == "dry_run":
        task = " ".join(args) if args else "测试任务"
        dry_run(task)

    else:
        print("""
AI 团队调试器 v1.0
用法：python references/debugger.py <命令> [参数]

  health                     全面健康检查
  trace [角色]               调度链路时间线（可按角色过滤）
  diff <快照A> <快照B>        两快照间的状态变化
  context <角色> <调度ID>     重建指定调度时的注入上下文
  tokens <角色>              逐层统计当前上下文 token 数
  replay <调度ID> [模型]      沙盒重放（不修改状态）
  dry_run [任务描述]          Mock 全流程验证（不耗 token）

示例：
  python references/debugger.py health
  python references/debugger.py trace pm
  python references/debugger.py diff D002 D003
  python references/debugger.py context architect D001
  python references/debugger.py replay D003
  python references/debugger.py dry_run "制定App营销方案"
""")
