"""
AI 团队 — 统一状态管理器 v2.0
============================
解决三个核心问题：
  1. 状态漂移   → 单一 master.json，所有读写经过此模块
  2. 上下文膨胀 → 三层注入：Hot(近3条) / Warm(摘要) / Cold(归档)
  3. 无回滚     → 每次写入前自动快照，支持按调度ID或时间戳回滚

目录结构：
  state/
  ├── master.json          ← 唯一真相来源
  ├── snapshots/           ← 自动快照（写前拍摄）
  │   └── snap_D001.json
  └── summaries/           ← 预计算摘要（防止注入膨胀）
      └── {role}_hot.txt
"""

import json
import shutil
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_write_lock = threading.Lock()  # 并发写入保护


STATE_DIR    = Path("state")
MASTER_PATH  = STATE_DIR / "master.json"
SNAP_DIR     = STATE_DIR / "snapshots"
SUMM_DIR     = STATE_DIR / "summaries"
SCHEMA_VER   = "2.0"

# 每个角色最多保留多少条"热历史"（直接注入上下文的）
HOT_WINDOW   = 3
# 快照最多保留多少个（超出后删最旧的）
MAX_SNAPS    = 30
# 角色insights超过多少条时触发自动摘要
INSIGHT_COMPRESS_AT = 10


# ═══════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _load_master() -> dict:
    if not MASTER_PATH.exists():
        raise FileNotFoundError(
            "state/master.json 不存在，请先运行 init_project() 初始化项目。"
        )
    with open(MASTER_PATH, encoding="utf-8") as f:
        data = json.load(f)
    ver = data.get("_meta", {}).get("schema_version")
    if ver != SCHEMA_VER:
        raise RuntimeError(
            f"Schema 版本不匹配（文件={ver}，当前={SCHEMA_VER}）。"
            f"请运行 migrate_state() 或用 rollback_to_snap() 恢复旧版本。"
        )
    return data

def _save_master(data: dict, *, snapshot_label: Optional[str] = None) -> str:
    """
    写入 master.json。
    写入前自动拍快照（snapshot_label 通常为调度ID，如 "D005"）。
    返回快照文件名（供调用方记录到日志）。
    """
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    SUMM_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 拍快照（写前）
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = snapshot_label or "auto"
    snap_name = f"snap_{label}_{ts}.json"
    snap_path = SNAP_DIR / snap_name

    if MASTER_PATH.exists():
        shutil.copy2(MASTER_PATH, snap_path)

    # 2. 清理旧快照（保留最新 MAX_SNAPS 个）
    snaps = sorted(SNAP_DIR.glob("snap_*.json"), key=lambda p: p.stat().st_mtime)
    for old in snaps[:-MAX_SNAPS]:
        old.unlink()

    # 3. 更新 checkpoints 索引并一次性写入（锁内完成，消除二次写竞态）
    data["_meta"]["schema_version"] = SCHEMA_VER
    data.setdefault("checkpoints", []).append({
        "snap_file": snap_name,
        "label":     label,
        "ts":        _now(),
        "sha256":    hashlib.sha256(json.dumps(data, ensure_ascii=False, indent=2).encode()).hexdigest()[:12],
    })
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    with _write_lock:
        MASTER_PATH.write_text(raw, encoding="utf-8")

    return snap_name


# ═══════════════════════════════════════════════════════
# 公共 API — 初始化
# ═══════════════════════════════════════════════════════

def init_project(name: str) -> str:
    """初始化新项目，返回 project_id。"""
    STATE_DIR.mkdir(exist_ok=True)
    proj_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M')}"

    template = _blank_master(proj_id, name)
    MASTER_PATH.write_text(
        json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (STATE_DIR / "snapshots").mkdir(exist_ok=True)
    (STATE_DIR / "summaries").mkdir(exist_ok=True)

    print(f"✅ 项目已初始化：{name}（{proj_id}）")
    return proj_id

def _blank_master(proj_id: str, name: str) -> dict:
    return {
        "_meta": {"schema_version": SCHEMA_VER, "created_at": _now()},
        "project": {
            "id": proj_id, "name": name,
            "created_at": _now(), "updated_at": _now(),
            "status": "in_progress", "current_phase": "初始化",
            "overall_progress": 0, "phases": [], "deliverables": [],
            "active_dispatches": [], "blockers": [],
            "decisions_log": [], "next_action": "", "team_notes": ""
        },
        "roles": {r: _blank_role() for r in
            ["pm","product","architect","ux","dba",
             "frontend","backend","reviewer","devops","debug","tester"]},
        "checkpoints": []
    }

def _blank_role() -> dict:
    return {
        "last_active": None, "session_count": 0,
        "completed_tasks": [], "current_tasks": [],
        "insights": [], "pending_followups": []
    }


# ═══════════════════════════════════════════════════════
# 公共 API — 读
# ═══════════════════════════════════════════════════════

def get_project() -> dict:
    """返回 project 块。"""
    return _load_master()["project"]

def get_role(role: str) -> dict:
    """返回指定角色的状态块。"""
    return _load_master()["roles"][role]

def list_checkpoints() -> list:
    """返回所有快照记录（最新在后）。"""
    data = _load_master()
    return data.get("checkpoints", [])


# ═══════════════════════════════════════════════════════
# 公共 API — 写
# ═══════════════════════════════════════════════════════

def update_project(patch: dict, *, dispatch_id: Optional[str] = None) -> str:
    """
    更新 project 块（patch 中只需包含要改的字段）。
    自动快照，返回快照文件名。
    """
    data = _load_master()
    data["project"].update(patch)
    data["project"]["updated_at"] = _now()
    return _save_master(data, snapshot_label=dispatch_id or "proj_update")

def complete_task(
    role: str,
    dispatch_id: str,
    task_summary: str,
    output_file: Optional[str],
    key_insights: Optional[list] = None,
) -> str:
    """
    角色完成任务后调用：
    - 将任务从 current_tasks 移入 completed_tasks（热层）
    - 追加 key_insights
    - 如果 insights 超出阈值，自动压缩为摘要（防膨胀）
    - 写前自动快照
    返回快照文件名。
    """
    data  = _load_master()
    role_data = data["roles"][role]

    # 移动任务记录
    role_data["current_tasks"] = [
        t for t in role_data["current_tasks"] if t.get("dispatch_id") != dispatch_id
    ]
    role_data["completed_tasks"].append({
        "dispatch_id":  dispatch_id,
        "summary":      task_summary,
        "output_file":  output_file,
        "completed_at": _now(),
    })
    role_data["last_active"]   = _now()
    role_data["session_count"] += 1

    # 追加洞察
    for ins in (key_insights or []):
        role_data["insights"].append({"text": ins, "ts": _now()})

    # 自动压缩：insights 超出阈值时把旧的折叠成一条摘要
    if len(role_data["insights"]) > INSIGHT_COMPRESS_AT:
        old     = role_data["insights"][:-HOT_WINDOW]
        hot     = role_data["insights"][-HOT_WINDOW:]
        summary = f"[压缩摘要 {_now()}] " + "；".join(i["text"] for i in old)
        role_data["insights"] = [{"text": summary, "ts": _now(), "compressed": True}] + hot
        # 同时写入 summaries 目录，供 build_context 调用
        summ_path = SUMM_DIR / f"{role}_compressed.txt"
        with open(summ_path, "a", encoding="utf-8") as f:
            f.write(summary + "\n")

    snap = _save_master(data, snapshot_label=dispatch_id)
    return snap

def mark_task_started(role: str, dispatch_id: str, task_desc: str) -> None:
    """角色开始任务时调用（无需快照，只记录当前任务）。"""
    data = _load_master()
    data["roles"][role]["current_tasks"].append({
        "dispatch_id": dispatch_id,
        "description": task_desc,
        "started_at":  _now(),
    })
    # 开始任务不触发快照（只有写 completed 才快照），但需要加锁防并发覆写
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    with _write_lock:
        MASTER_PATH.write_text(raw, encoding="utf-8")


# ═══════════════════════════════════════════════════════
# 公共 API — 回滚
# ═══════════════════════════════════════════════════════

def rollback_to_snap(snap_file: str) -> None:
    """
    回滚到指定快照。
    snap_file 可以是：
      - 完整文件名：snap_D003_20260509_143215.json
      - 调度ID前缀：D003（自动找最近的匹配快照）
      - 'last'      ：回滚到上一个快照
    """
    SNAP_DIR.mkdir(exist_ok=True)

    if snap_file == "last":
        snaps = sorted(SNAP_DIR.glob("snap_*.json"), key=lambda p: p.stat().st_mtime)
        if not snaps:
            raise FileNotFoundError("没有可用的快照。")
        target = snaps[-1]
    elif snap_file.endswith(".json"):
        target = SNAP_DIR / snap_file
    else:
        # 按 dispatch_id 前缀搜索
        candidates = sorted(
            SNAP_DIR.glob(f"snap_{snap_file}_*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        if not candidates:
            raise FileNotFoundError(f"找不到匹配 {snap_file!r} 的快照。")
        target = candidates[-1]

    if not target.exists():
        raise FileNotFoundError(f"快照文件不存在：{target}")

    # 把当前 master 先备份一份（以防误回滚）
    safety = SNAP_DIR / f"snap_pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if MASTER_PATH.exists():
        shutil.copy2(MASTER_PATH, safety)

    shutil.copy2(target, MASTER_PATH)
    print(f"✅ 已回滚到快照：{target.name}（当前状态已备份到 {safety.name}）")

def rollback_to_dispatch(dispatch_id: str) -> None:
    """
    回滚到某次调度之前的状态。
    等价于 rollback_to_snap(dispatch_id)，但更语义化。
    """
    rollback_to_snap(dispatch_id)


def list_snaps(n: int = 10) -> list:
    """列出最近 n 个快照（最新在前）。"""
    snaps = sorted(
        SNAP_DIR.glob("snap_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:n]
    return [
        {"file": p.name, "size_kb": round(p.stat().st_size / 1024, 1),
         "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
        for p in snaps
    ]


# ═══════════════════════════════════════════════════════
# 公共 API — 上下文注入（防膨胀）
# ═══════════════════════════════════════════════════════

def build_context(role: str, task: str) -> str:
    """
    构建注入给角色的上下文（模型无关格式）。

    三层结构，总量约 600 tokens，不随项目时长增长：
      Warm: 项目摘要（进度、阶段、下一步、团队备注）
      Hot:  该角色最近 3 条任务 + 3 条关键洞察
      Task: 当次任务 + state_update 格式要求

    输出使用纯文本 + XML 标签，兼容所有主流大模型。
    """
    data = _load_master()
    proj = data["project"]
    rd   = data["roles"][role]

    # ── Warm 层（约 100 tokens）────────────────────────
    decisions = proj.get("decisions_log", [])[-2:]
    dec_text  = ""
    if decisions:
        dec_text = "\n近期决策：" + "；".join(d["decision"] for d in decisions)

    warm = (
        f"项目名称：{proj['name']}（ID：{proj['id']}）\n"
        f"当前进度：{proj['overall_progress']}% | 阶段：{proj['current_phase']}\n"
        f"下一步行动：{proj['next_action'] or '待 PM 决定'}"
        f"{dec_text}\n"
        f"团队备注：{proj.get('team_notes') or '无'}"
    )

    # ── Hot 层（约 200 tokens）────────────────────────
    recent = rd["completed_tasks"][-HOT_WINDOW:]
    if recent:
        tasks_text = "\n".join(
            f"  - [{t['dispatch_id']}] {t['summary']}"
            + (f"（输出：{t['output_file']}）" if t.get("output_file") else "")
            for t in recent
        )
        hot = f"你在本项目已完成的任务（最近 {len(recent)} 条）：\n{tasks_text}"
    else:
        hot = "你在本项目尚无历史任务记录（首次调用）。"

    insights = rd["insights"][-HOT_WINDOW:]
    if insights:
        ins_lines = "\n".join(f"  - {i['text']}" for i in insights)
        hot += f"\n\n你积累的关键洞察：\n{ins_lines}"

    followups = rd.get("pending_followups", [])
    if followups:
        hot += f"\n\n你标记的待跟进事项：\n" + "\n".join(f"  - {f}" for f in followups)

    # ── 组装（纯文本，任何模型均可理解）─────────────────
    return (
        f"<warm_context>\n{warm}\n</warm_context>\n\n"
        f"<hot_context>\n{hot}\n</hot_context>\n\n"
        f"<task>\n{task}\n</task>\n\n"
        "完成任务后，在回复末尾附上以下格式的状态更新（JSON，勿省略）：\n"
        "<state_update>\n"
        '{"summary": "一句话：你做了什么、最重要的结论是什么",\n'
        ' "output_file": "outputs/文件名.md（如无文件则填 null）",\n'
        ' "insights": ["本次新增的重要洞察，供后续角色参考"]}\n'
        "</state_update>"
    )


def parse_state_update(role: str, dispatch_id: str, llm_output: str) -> bool:
    """
    从 LLM 输出中提取 <state_update>，调用 complete_task 写入。
    返回是否成功解析。
    """
    import re
    match = re.search(r"<state_update>\s*([\s\S]+?)\s*</state_update>", llm_output)
    if not match:
        print(f"⚠️  {role} 的输出未包含 <state_update>，状态未更新。")
        return False

    try:
        upd = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"⚠️  <state_update> JSON 解析失败：{e}")
        return False

    snap = complete_task(
        role        = role,
        dispatch_id = dispatch_id,
        task_summary= upd.get("summary", "（无摘要）"),
        output_file = upd.get("output_file"),
        key_insights= upd.get("insights", []),
    )
    print(f"✅  {role} 状态已更新（快照：{snap}）")
    return True


# ═══════════════════════════════════════════════════════
# 公共 API — 迁移（Schema 升级）
# ═══════════════════════════════════════════════════════

def migrate_state(old_state_dir: str = "state") -> None:
    """
    将 v1.0（10个分散JSON）迁移到 v2.0（单一 master.json）。
    迁移前自动备份原始文件。
    """
    old = Path(old_state_dir)
    backup_dir = old / "v1_backup"
    backup_dir.mkdir(exist_ok=True)

    proj_file = old / "project_state.json"
    if not proj_file.exists():
        print("找不到 v1 的 project_state.json，跳过迁移。")
        return

    with open(proj_file, encoding="utf-8") as f:
        old_proj = json.load(f)

    proj_id   = old_proj.get("project_id") or f"proj_migrated_{datetime.now().strftime('%Y%m%d')}"
    proj_name = old_proj.get("project_name", "迁移项目")

    master = _blank_master(proj_id, proj_name)
    master["project"].update({
        k: v for k, v in old_proj.items()
        if k in master["project"] and v is not None
    })

    ROLE_FILE_MAP = {
        "pm": "pm_state.json", "researcher": "researcher_state.json",
        "writer": "writer_state.json", "developer": "developer_state.json",
        "analyst": "analyst_state.json", "qa": "qa_state.json",
        "marketer": "marketer_state.json", "designer": "designer_state.json",
        "tester": "tester_state.json",
    }
    for role, fname in ROLE_FILE_MAP.items():
        fp = old / fname
        if fp.exists():
            with open(fp, encoding="utf-8") as f:
                old_role = json.load(f)
            for task in old_role.get("completed_tasks", []):
                master["roles"][role]["completed_tasks"].append({
                    "dispatch_id":  task.get("task_id", "legacy"),
                    "summary":      task.get("description", task.get("task", "")),
                    "output_file":  task.get("output_file"),
                    "completed_at": task.get("completed_at"),
                })
            for ins in old_role.get("knowledge_base", {}).get("accumulated_insights", []):
                master["roles"][role]["insights"].append({"text": ins, "ts": None})
            shutil.copy2(fp, backup_dir / fname)

    shutil.copy2(proj_file, backup_dir / "project_state.json")

    MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 迁移完成。原始文件备份在 {backup_dir}。请验证 state/master.json 后删除旧文件。")


# ═══════════════════════════════════════════════════════
# CLI 快速操作（直接运行此文件时）
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "init":
        name = sys.argv[2] if len(sys.argv) > 2 else "新项目"
        init_project(name)

    elif cmd == "status":
        p = get_project()
        print(f"项目：{p['name']}（{p['id']}）")
        print(f"进度：{p['overall_progress']}% | 阶段：{p['current_phase']}")
        print(f"下一步：{p['next_action']}")

    elif cmd == "snaps":
        snaps = list_snaps(15)
        print(f"最近 {len(snaps)} 个快照：")
        for s in snaps:
            print(f"  {s['file']}  {s['size_kb']}KB  {s['mtime']}")

    elif cmd == "rollback":
        target = sys.argv[2] if len(sys.argv) > 2 else "last"
        rollback_to_snap(target)

    elif cmd == "checkpoints":
        cps = list_checkpoints()
        print(f"共 {len(cps)} 个 checkpoint：")
        for cp in cps[-10:]:
            print(f"  [{cp['label']}] {cp['ts']}  {cp['snap_file']}")

    elif cmd == "migrate":
        migrate_state()

    else:
        print("""
AI 团队 State Manager v2.0
用法：
  python state_manager.py init "项目名"     初始化新项目
  python state_manager.py status            查看当前项目状态
  python state_manager.py snaps             列出最近快照
  python state_manager.py checkpoints       列出所有 checkpoint
  python state_manager.py rollback [target] 回滚（target=快照名/调度ID/last）
  python state_manager.py migrate           从 v1 迁移到 v2
""")
