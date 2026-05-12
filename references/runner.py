"""
runner.py — Multi-Agent DAG 执行引擎
======================================
把 PM 规划的任务图（DAG）转成真正的并行执行。

DAG 格式（PM 输出后由此模块解析执行）：
  [
    # 第一层：可以同时跑
    [{"role": "product",   "task": "澄清需求编写用户故事", "id": "T001"},
     {"role": "architect", "task": "设计系统架构",       "id": "T002"}],

    # 第二层：等第一层全部完成后才开始
    [{"role": "frontend",  "task": "实现前端功能",       "id": "T003",
      "depends_on": ["T001", "T002"]},
     {"role": "backend",   "task": "实现后端API",        "id": "T004",
      "depends_on": ["T001"]}],

    # 第三层
    [{"role": "tester", "task": "执行集成测试", "id": "T005",
      "depends_on": ["T003", "T004"]}],
  ]

核心特性：
  1. asyncio.gather() 并行执行同层任务
  2. Agent 完成后结果自动发到消息总线
  3. 下游 Agent 从总线读取上游结果作为输入
  4. 支持 Agent 在执行中发起 sub_request（临时请求其他 Agent）
  5. 失败重试（可配置次数）
  6. 超时控制（每个 Agent 有独立超时）
"""

import asyncio
import json
import logging
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("runner")

sys.path.insert(0, str(Path(__file__).parent))

from message_bus import MessageBus, get_bus, TASK, RESULT, REQUEST, INFO, ALL_ROLES
from model_adapter import (call_role, load_system_prompt,
                            get_role_timeout,
                            reset_token_usage, compute_usage_summary)
from state_manager    import (build_context, mark_task_started,
                               parse_state_update, update_project,
                               get_project)
from knowledge_base    import build_kb_context, init_knowledge_base
from resource_library  import build_library_context, init_resource_library
from doc_generator     import generate_all_docs
from logger            import init_logger, get_logger

# ── 配置（优先从 config/workflow.yaml 读取，有硬编码 fallback）─
try:
    from config_loader import get_workflow_value as _wcfg
except ImportError:
    _wcfg = lambda k, d: d

DEFAULT_TIMEOUT        = _wcfg("default_timeout", 180)
DEFAULT_RETRIES        = _wcfg("default_retries", 2)
MAX_SUB_REQUESTS       = _wcfg("max_sub_requests", 3)
MAX_SUB_REQUEST_DEPTH  = _wcfg("max_sub_request_depth", 2)
QA_DBG_MAX_ITER        = _wcfg("qa_dbg_max_iter", 3)
AUTO_APPROVE           = _wcfg("auto_approve", False)
VALID_ROLES            = set(ALL_ROLES) | {"_approval"}  # 合法角色名（含审批虚拟节点）


# ═══════════════════════════════════════════════════
# 单 Agent 执行
# ═══════════════════════════════════════════════════

async def run_agent(
    task_node:  dict,
    results:    dict,
    bus:        MessageBus,
    retries:    int = DEFAULT_RETRIES,
    timeout:    int = DEFAULT_TIMEOUT,
    provider:   Optional[str] = None,
    depth:      int = 0,  # sub_request 递归深度
) -> dict:
    """
    执行单个 Agent 任务节点。

    task_node 格式：
      {"role": "product", "task": "澄清需求", "id": "T001",
       "depends_on": ["T000"]}

    返回：
      {"id": "T001", "role": "product", "status": "done",
       "output": "...", "snap": "snap_T001_...json"}
    """
    # 特殊节点：人工审批
    if task_node.get("role") == "_approval":
        return await _request_human_approval(task_node, results)

    role    = task_node["role"]
    task_id = task_node["id"]
    task    = task_node["task"]

    slog = get_logger()
    slog.log("info", "task_started", role=role, dispatch_id=task_id,
             phase="executing", summary=task[:80])

    logger.info(f"  → [{task_id}] {role.upper()} 开始：{task[:40]}")

    # 收集上游依赖的输出，注入到任务描述
    upstream_ctx = _collect_upstream(task_node, results, bus)

    for attempt in range(retries + 1):
        try:
            result = await asyncio.wait_for(
                _call_agent_async(role, task, task_id, upstream_ctx, bus, provider, depth=depth),
                timeout=timeout,
            )
            logger.info(f"  ✓ [{task_id}] {role.upper()} 完成")

            slog.log("info", "task_completed", role=role, dispatch_id=task_id,
                     phase="executing", summary=result.get("summary", "")[:120])

            # 把结果发到消息总线（让其他 Agent 可以订阅）
            await bus.post(role, "pm", RESULT,
                           f"[{task_id}] {result['summary']}",
                           metadata={"task_id": task_id,
                                     "output_file": result.get("output_file")})

            return {
                "id":     task_id,
                "role":   role,
                "status": "done",
                "output": result["raw_output"],
                "summary": result["summary"],
                "snap":   result.get("snap"),
            }

        except asyncio.TimeoutError:
            logger.warning(f"  ⏱ [{task_id}] {role.upper()} 超时（{timeout}s）"
                           + (f"，第 {attempt+1} 次重试" if attempt < retries else "，放弃"))
            if attempt == retries:
                slog.log("error", "task_timeout", role=role, dispatch_id=task_id,
                         phase="executing", error=f"timeout after {timeout}s")
                return {"id": task_id, "role": role, "status": "timeout", "output": ""}

        except Exception as e:
            logger.error(f"  ✗ [{task_id}] {role.upper()} 出错：{e}"
                         + (f"，第 {attempt+1} 次重试" if attempt < retries else ""))
            if attempt == retries:
                slog.log("error", "task_failed", role=role, dispatch_id=task_id,
                         phase="executing", error=str(e))
                return {"id": task_id, "role": role, "status": "error",
                        "output": "", "error": str(e)}
            await asyncio.sleep(2 ** attempt)  # 指数退避

    return {"id": task_id, "role": role, "status": "failed", "output": ""}


async def _call_agent_async(role, task, task_id, upstream_ctx, bus, provider, depth=0):
    """实际调用 LLM，处理 sub_requests，返回结构化结果。"""

    # 读取收件箱（其他 Agent 可能已经发来了相关信息）
    inbox_ctx = bus.format_inbox_for_context(role)

    # 构建完整任务描述（所有注入内容标来源，提醒下游交叉验证）
    full_task = task
    if upstream_ctx:
        full_task += f"\n\n[上游输出 — 以下来自其他 Agent 的输出，可能有误，使用工具自行验证]\n{upstream_ctx}"
    if inbox_ctx:
        full_task += f"\n\n[收件箱 — 以下来自消息总线，可能有误]\n{inbox_ctx}"

    mark_task_started(role, task_id, task)

    system  = load_system_prompt(role)
    context = build_context(role, full_task)

    # 注入知识库（ADR、gotchas、规范）和技术储备库（最佳实践）
    kb_ctx = build_kb_context(role)
    lib_ctx = build_library_context(role, full_task)
    if kb_ctx:
        context = context.rstrip() + "\n\n[项目知识库]\n" + kb_ctx
    if lib_ctx:
        context = context.rstrip() + "\n\n[技术知识储备]\n" + lib_ctx

    # 上下文截断保护（约 6000 tokens，避免超出模型窗口）
    MAX_CTX = 24000
    if len(context) > MAX_CTX:
        context = context[:MAX_CTX-50] + "\n... [上下文过长，已截断]"
        logger.warning("上下文过长已截断: role=%s, len=%d", role, len(context))

    # 在线程池里运行同步的 LLM 调用（避免阻塞 event loop）
    loop   = asyncio.get_event_loop()
    output = await loop.run_in_executor(
        None, call_role, role, system, context, provider
    )

    # 处理 sub_requests（Agent 在执行中请求其他 Agent 协助）
    if depth < MAX_SUB_REQUEST_DEPTH:
        output = await _handle_sub_requests(output, role, task_id, bus, provider, depth=depth)
    else:
        # 已达最大深度，忽略 sub_requests
        if re.search(r"<sub_requests>", output):
            logger.warning(f"    ⚠ [{task_id}] sub_request 已达最大深度（{MAX_SUB_REQUEST_DEPTH}），已忽略")
            output = re.sub(r"<sub_requests>[\s\S]*?</sub_requests>",
                           f"\n[已达到 sub_request 最大深度 {MAX_SUB_REQUEST_DEPTH}，请求被忽略]\n",
                           output)

    # 解析 state_update
    parse_state_update(role, task_id, output)

    # 提取摘要
    summary = _extract_summary(output)
    snap    = _latest_snap(task_id)

    return {"raw_output": output, "summary": summary, "snap": snap}


# ═══════════════════════════════════════════════════
# Sub-requests：Agent 在执行中请求其他 Agent
# ═══════════════════════════════════════════════════

async def _handle_sub_requests(output: str, requester: str,
                                task_id: str, bus: MessageBus,
                                provider: Optional[str], depth: int = 0) -> str:
    """
    从 Agent 输出中提取 <sub_requests> 块，
    为每个请求调用对应 Agent，把结果注入回原输出。

    Agent 可以在输出中包含：
    <sub_requests>
    [{"to": "backend",  "task": "请补充 API 认证中间件"},
     {"to": "frontend", "task": "请澄清状态管理方案"}]
    </sub_requests>
    """
    m = re.search(r"<sub_requests>\s*([\s\S]+?)\s*</sub_requests>", output)
    if not m:
        return output

    try:
        requests = json.loads(m.group(1))[:MAX_SUB_REQUESTS]
    except json.JSONDecodeError:
        return output

    if not requests:
        return output

    logger.info(f"    ↳ {requester.upper()} 发起 {len(requests)} 个 sub_request")
    slog = get_logger()
    slog.log("info", "sub_request_spawned", role=requester, dispatch_id=task_id,
             phase="executing",
             summary=f"spawned {len(requests)} sub-requests: {[r.get('to','?') for r in requests]}")

    # 并行处理所有 sub_requests（校验目标角色合法性）
    sub_tasks = []
    for i, req in enumerate(requests):
        target = req.get("to", "")
        if target not in VALID_ROLES:
            logger.warning(f"    ⚠ sub_request 目标角色 '{target}' 无效，已忽略")
            sub_tasks.append(None)  # 占位，保持索引对齐
            continue
        sub_id = f"{task_id}_sub{i+1}"
        sub_node = {"role": target, "task": req["task"], "id": sub_id}

        # 通知消息总线
        await bus.post(requester, target, REQUEST, req["task"],
                       metadata={"parent_task": task_id, "sub_id": sub_id})

        sub_tasks.append((sub_node, provider))

    # 执行有效请求（None 占位跳过，传递 depth+1）
    async def _safe_run(node_provider):
        if node_provider is None:
            return {"status": "skipped", "output": "", "summary": "目标角色无效，已跳过"}
        node, prov = node_provider
        return await run_agent(node, {}, bus, provider=prov, depth=depth + 1)

    sub_results = await asyncio.gather(*[_safe_run(st) for st in sub_tasks], return_exceptions=True)

    # 把 sub_request 结果注入到原始输出
    injected = "\n\n[Sub-agent 协助结果]\n"
    for req, res in zip(requests, sub_results):
        if isinstance(res, Exception):
            injected += f"- {req['to'].upper()}：执行出错\n"
        elif isinstance(res, dict):
            if res.get("status") == "done":
                injected += f"- {req['to'].upper()}：{res.get('summary','')}\n"
            elif res.get("status") == "skipped":
                injected += f"- {req['to'].upper()}：已忽略（目标角色无效）\n"
            else:
                injected += f"- {req['to'].upper()}：未完成\n"
        else:
            injected += f"- {req['to'].upper()}：未知错误\n"

    # 移除 sub_requests 块，追加结果
    output = re.sub(r"<sub_requests>[\s\S]*?</sub_requests>", "", output)
    output += injected

    return output


# ═══════════════════════════════════════════════════
# DAG 执行引擎
# ═══════════════════════════════════════════════════

async def run_dag(
    dag:      list[list[dict]],
    provider: Optional[str] = None,
    on_tier_complete: Optional[callable] = None,
    skip_tasks: Optional[set[str]] = None,
) -> dict:
    """
    执行 DAG。每一层的任务并行运行，层与层之间串行。

    dag: [ tier1_tasks, tier2_tasks, ... ]
    每个 task: {"role": str, "task": str, "id": str, "depends_on": list}
    skip_tasks: 已完成的 task_id 集合（断点续跑时跳过）

    返回所有任务的结果 {task_id: result_dict}
    """
    bus     = get_bus()
    results = {}
    skip    = skip_tasks or set()
    failed_ids = set()  # 追踪失败的任务 ID，用于阻断下游

    total_tasks = sum(len(tier) for tier in dag)
    done_tasks  = 0

    logger.info(f"\n  DAG 执行开始：{len(dag)} 层，共 {total_tasks} 个任务"
                + (f"（{len(skip)} 个已跳过）" if skip else ""))
    logger.info(f"  {'─'*50}")

    for tier_idx, tier in enumerate(dag):
        # 过滤掉已完成的 task（断点续跑）
        active_nodes = []
        skipped_results = {}
        for node in tier:
            if node["id"] in skip:
                from state_manager import get_role
                role_state = get_role(node["role"])
                last = role_state["completed_tasks"][-1] if role_state.get("completed_tasks") else None
                skipped_results[node["id"]] = {
                    "id": node["id"], "role": node["role"], "status": "done",
                    "output": f"(恢复：崩溃前已完成 {node['id']})",
                    "summary": last["summary"] if last else "已恢复",
                    "snap": _latest_snap(node["id"]),
                }
                logger.info(f"  ↻ [{node['id']}] {node['role'].upper()} 跳过（崩溃前已完成）")
            elif set(node.get("depends_on", [])) & failed_ids:
                # 上游关键任务失败，阻断本任务
                blocked_by = set(node.get("depends_on", [])) & failed_ids
                results[node["id"]] = {
                    "id": node["id"], "role": node["role"],
                    "status": "blocked", "output": "",
                    "error": f"上游任务失败，依赖未满足：{sorted(blocked_by)}"
                }
                logger.warning(f"  ⊘ [{node['id']}] {node['role'].upper()} 阻断"
                               f"（上游失败：{sorted(blocked_by)}）")
            else:
                active_nodes.append(node)

        if not active_nodes:
            results.update(skipped_results)
            continue

        logger.info(f"\n  [第 {tier_idx+1} 层] 并行执行 {len(active_nodes)} 个任务")

        # 并行执行本层所有任务（使用角色独立超时）
        tier_tasks = [
            run_agent(node, results, bus,
                      timeout=get_role_timeout(node["role"], provider),
                      provider=provider)
            for node in active_nodes
        ]
        tier_results = await asyncio.gather(*tier_tasks, return_exceptions=True)

        results.update(skipped_results)

        # 收集结果，追踪失败
        for node, res in zip(active_nodes, tier_results):
            if isinstance(res, Exception):
                logger.error(f"  ✗ [{node['id']}] 异常：{res}")
                results[node["id"]] = {
                    "id": node["id"], "role": node["role"],
                    "status": "exception", "output": "", "error": str(res)
                }
                failed_ids.add(node["id"])
            else:
                results[node["id"]] = res
                if res.get("status") not in ("done",):
                    failed_ids.add(node["id"])
            done_tasks += 1

        # 本层完成后的回调（可用于更新项目状态）
        if on_tier_complete:
            await on_tier_complete(tier_idx, tier, results)

        # 统计本层失败
        tier_failed = [r for r in tier_results
                       if isinstance(r, dict) and r.get("status") not in ("done",)]
        if tier_failed:
            failed_names = [f"{n['id']}({n['role']})" for n, r in zip(active_nodes, tier_results)
                           if isinstance(r, dict) and r.get("status") not in ("done",)]
            logger.warning(f"\n  ⚠ 第 {tier_idx+1} 层有 {len(tier_failed)} 个任务失败：{', '.join(failed_names)}")
            if failed_ids:
                logger.warning(f"  下游依赖 {sorted(failed_ids)} 的任务将被自动阻断")

    logger.info(f"\n  {'─'*50}")
    done  = sum(1 for r in results.values() if r.get("status") == "done")
    total = len(results)
    logger.info(f"  DAG 执行完成：{done}/{total} 成功\n")

    return results


# ═══════════════════════════════════════════════════
# 完整项目运行入口
# ═══════════════════════════════════════════════════

async def run_project(user_task: str, provider: Optional[str] = None) -> str:
    """
    端到端执行一个项目任务：
      1. PM 规划 DAG
      2. DAG 预览（人工确认）
      3. Runner 并行执行
      4. QA→DBG→QA 循环（最多 QA_DBG_MAX_ITER 次）
      5. PM 整合结果
      6. Token 用量报告

    支持断点续跑：已完成的 task 会自动跳过（基于快照检测）。
    """
    bus = get_bus()
    reset_token_usage()
    init_knowledge_base()    # 项目知识库
    init_resource_library()  # 技术知识储备库

    # 初始化结构化日志（用项目名做 project_id）
    try:
        proj = get_project()
        pid = proj.get("name", "").replace(" ", "_")[:40] if proj else ""
    except Exception:
        pid = ""
    if not pid:
        from datetime import datetime as _dt
        pid = f"proj_{_dt.now().strftime('%Y%m%d_%H%M')}"
    init_logger(pid)
    slog = get_logger()
    slog.log("info", "project_started", phase="planning",
             summary=user_task[:120])

    # ── Step 1：PM 规划 ──────────────────────────────
    # 检查是否为断点续跑：已有快照则跳过重新规划
    pending_from_crash = _find_completed_tasks_from_snapshots()

    if pending_from_crash:
        logger.info(f"\n  [恢复] 检测到未完成的项目，跳过 PM 重规划（{len(pending_from_crash)} 个任务已完成）")
        dag = _load_default_dag(user_task)
    else:
        logger.info("  [PM] 规划任务...")
        mark_task_started("pm", "D000", user_task)
        context    = build_context("pm", user_task)
        pm_plan    = await asyncio.get_event_loop().run_in_executor(
            None, call_role, "pm", load_system_prompt("pm"), context, provider
        )
        parse_state_update("pm", "D000", pm_plan)

        # 从 PM 输出中提取 DAG（或用默认流程）
        dag = _extract_dag(pm_plan, user_task)

        # ── Step 1.4：DAG 校验 ──────────────────────
        dag_issues = _validate_dag(dag)
        if dag_issues:
            logger.warning("  [校验] DAG 存在问题，使用默认流程：")
            for issue in dag_issues:
                logger.warning(f"    - {issue}")
            dag = _load_default_dag(user_task)

        # ── Step 1.5：DAG 预览 & 确认 ────────────────
        approved = await _request_dag_approval(dag)
        if not approved:
            logger.info("  [PM] 重新规划（用户驳回了 DAG）...")
            pm_plan = await asyncio.get_event_loop().run_in_executor(
                None, call_role, "pm", load_system_prompt("pm"),
                f"{user_task}\n\n【以上方案被驳回，请重新规划 DAG，避免重复之前的方案】", provider
            )
            parse_state_update("pm", "D_replan", pm_plan)
            dag = _extract_dag(pm_plan, user_task)
            logger.info(_format_dag_preview(dag))

    # ── Step 2：并行执行 DAG（断点续跑：跳过已完成 task） ──
    slog.log("info", "phase_change", phase="executing", summary="DAG 执行开始")
    completed = _find_completed_tasks_from_snapshots()

    async def on_tier_done(tier_idx, tier, results):
        done = sum(1 for r in results.values() if r.get("status") == "done")
        update_project({
            "overall_progress": int(done / max(sum(len(t) for t in dag), 1) * 60),
            "current_phase":    f"第 {tier_idx+1} 层执行中",
        })

    all_results = await run_dag(dag, provider=provider,
                                on_tier_complete=on_tier_done,
                                skip_tasks=completed)

    # ── Step 3：QA→DBG→QA 循环 ──────────────────────
    # 找 DAG 中最后一个 tester 角色的输出
    qa_iteration = 0
    last_tester_id = None
    for r in sorted(all_results.values(), key=lambda x: x.get("id", "")):
        if r.get("role") == "tester" and r.get("status") == "done":
            last_tester_id = r["id"]

    while last_tester_id and qa_iteration < QA_DBG_MAX_ITER:
        tester_result = all_results.get(last_tester_id, {})
        if not _tester_found_bugs(tester_result):
            if qa_iteration > 0:
                logger.info(f"\n  ✅ [QA↺{qa_iteration}] Bug 已修复，测试通过")
            break

        qa_iteration += 1
        bug_output = (tester_result.get("output", "") or "")[:1000]
        logger.warning(f"\n  🐛 [QA↺{qa_iteration}/{QA_DBG_MAX_ITER}] Tester 发现 Bug，交 Debug 修复")

        debug_id = f"DBG_{qa_iteration}"
        retest_id = f"RETEST_{qa_iteration}"
        mini_dag = [
            [{"role": "debug",  "task": f"修复以下测试发现的 Bug：\n{bug_output}", "id": debug_id}],
            [{"role": "tester", "task": "回归测试，验证 Bug 是否已修复",           "id": retest_id,
              "depends_on": [debug_id]}],
        ]
        mini_results = await run_dag(mini_dag, provider=provider)
        all_results.update(mini_results)
        last_tester_id = retest_id

    # 达到上限仍有 Bug → 升级给人
    if qa_iteration == QA_DBG_MAX_ITER and _tester_found_bugs(all_results.get(last_tester_id, {})):
        logger.warning(f"\n  ⚠ [QA↺{QA_DBG_MAX_ITER}] 已达上限，Bug 仍未修复，记录到知识库")
        try:
            from knowledge_base import add_gotcha
            add_gotcha(
                title=f"QA→DBG 循环达上限（{QA_DBG_MAX_ITER} 轮）未修复",
                symptom="自动修复无法通过的测试用例",
                cause="需人工介入分析",
                solution="请人工排查并修复",
                affected_roles=["debug", "tester"],
            )
        except Exception:
            pass

    # ── Step 3.5：生成 API 文档 ──────────────────────
    try:
        doc_results = generate_all_docs()
        logger.info(f"  [文档] API 文档已生成：{', '.join(doc_results.values())}")
    except Exception as e:
        logger.warning(f"  [文档] 生成 API 文档失败（非致命）：{e}")

    # ── Step 4：PM 整合 ──────────────────────────────
    slog.log("info", "phase_change", phase="integrating", summary="PM 整合所有结果")
    logger.info("  [PM] 整合所有结果...")
    summaries = "\n".join(
        f"[{r['id']}] {r['role'].upper()}：{r.get('summary','')}"
        for r in all_results.values() if r.get("status") == "done"
    )
    final_context = build_context("pm",
        f"请整合以下各 Agent 的工作成果，生成最终交付报告：\n{summaries}")
    final_output = await asyncio.get_event_loop().run_in_executor(
        None, call_role, "pm", load_system_prompt("pm"), final_context, provider
    )
    parse_state_update("pm", "D_final", final_output)
    update_project({"overall_progress": 100, "status": "done",
                    "next_action": "已完成"})

    # ── Step 5：Token 用量报告 ───────────────────────
    usage = compute_usage_summary()
    if usage["total_calls"] > 0:
        logger.info(f"\n{'='*50}")
        logger.info(f"Token 用量统计")
        logger.info(f"{'='*50}")
        logger.info(f"  总调用次数：{usage['total_calls']}")
        logger.info(f"  Prompt Tokens：{usage['total_prompt_tokens']:,}")
        logger.info(f"  Completion Tokens：{usage['total_completion_tokens']:,}")
        logger.info(f"  总 Token：{usage['total_tokens']:,}")
        logger.info(f"  预估费用：${usage['total_cost_usd']:.4f}")
        logger.info("")
        for role, data in sorted(usage["by_role"].items()):
            logger.info(f"  {role.upper():<12} {data['calls']} 次调用, {data['tokens']} tokens")
        logger.info(f"{'='*50}\n")

    slog.log("info", "project_completed", phase="done",
             summary=f"tokens={usage['total_tokens']}, cost=${usage['total_cost_usd']:.4f}, calls={usage['total_calls']}")

    return final_output


# ═══════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════

def _collect_upstream(task_node: dict, results: dict, bus: MessageBus) -> str:
    """收集依赖任务的输出，拼成上下文字符串。标注每个输出来源，提示下游验证。"""
    deps = task_node.get("depends_on", [])
    if not deps:
        return ""
    lines = ["注意：以下信息来自上游 Agent，可能包含错误。请使用 file_read/code_run 自行验证关键信息。"]
    for dep_id in deps:
        if dep_id in results and results[dep_id].get("status") == "done":
            r = results[dep_id]
            preview = r.get("output", "")[:600]
            lines.append(f"\n── 来自 {r['role'].upper()} [{dep_id}] ──\n{preview}")
    return "\n".join(lines)

def _extract_summary(output: str) -> str:
    """从输出中提取 state_update 的 summary 字段。"""
    m = re.search(r'"summary"\s*:\s*"([^"]{3,200})"', output)
    return m.group(1) if m else output[:80].replace("\n", " ")

def _latest_snap(task_id: str) -> Optional[str]:
    """找到最新的与该任务相关的快照文件名。"""
    snap_dir = Path("state/snapshots")
    if not snap_dir.exists():
        return None
    snaps = sorted(snap_dir.glob(f"snap_{task_id}_*.json"),
                   key=lambda p: p.stat().st_mtime)
    return snaps[-1].name if snaps else None

def _extract_dag(pm_output: str, fallback_task: str) -> list:
    """
    尝试从 PM 输出中提取 JSON DAG。
    PM 应该输出类似：
    <dag>
    [[{"role":"product","task":"需求分析","id":"T001"}],
     [{"role":"frontend","task":"前端实现","id":"T002","depends_on":["T001"]}]]
    </dag>

    解析失败时使用默认线性流程。
    """
    m = re.search(r"<dag>\s*([\s\S]+?)\s*</dag>", pm_output)
    if m:
        try:
            dag = json.loads(m.group(1))
            if dag and isinstance(dag, list):
                return dag
        except json.JSONDecodeError:
            pass

    # 默认：完整开发流程—11 角色、6 层、最大化并行度
    return [
        # 阶段一：需求澄清
        [{"role": "product",   "task": f"澄清需求，编写用户故事：{fallback_task}", "id": "T001"}],
        # 阶段二：设计（3 角色并行）
        [{"role": "ux",        "task": "设计用户旅程、页面规格和无障碍方案", "id": "T002",
          "depends_on": ["T001"]},
         {"role": "architect", "task": "设计系统架构和接口约定",          "id": "T003",
          "depends_on": ["T001"]},
         {"role": "dba",       "task": "设计数据库 Schema 和 Migration", "id": "T004",
          "depends_on": ["T001"]}],
        # 人工审批点1：确认设计方案
        [{"role": "_approval", "task": "请确认需求规格、UX设计、架构方案和数据库设计", "id": "AP1",
          "depends_on": ["T002", "T003", "T004"]}],
        # 阶段三：实现（3 角色并行）
        [{"role": "frontend",  "task": "实现前端功能（含单元测试）",       "id": "T005",
          "depends_on": ["T002", "T003"]},
         {"role": "backend",   "task": "实现后端 API（含单元测试）",       "id": "T006",
          "depends_on": ["T003", "T004"]},
         {"role": "devops",    "task": "搭建 CI/CD 流水线和部署配置",      "id": "T007",
          "depends_on": ["T003"]}],
        # 阶段四：审查 + 测试（并行）
        [{"role": "reviewer",  "task": "审查 FE 和 BE 代码质量与安全性",   "id": "T008",
          "depends_on": ["T005", "T006"]},
         {"role": "tester",    "task": "执行集成测试、验收测试和边界用例",   "id": "T009",
          "depends_on": ["T005", "T006"]}],
        # 人工审批点2：发布确认
        [{"role": "_approval", "task": "审查和测试完成，请确认是否发布",     "id": "AP2",
          "depends_on": ["T008", "T009"]}],
    ]


# ═══════════════════════════════════════════════════
# DAG 校验
# ═══════════════════════════════════════════════════

def _validate_dag(dag: list[list[dict]]) -> list[str]:
    """
    校验 DAG 的合法性，返回问题列表（空列表表示通过）。

    检查项：
    1. 角色名是否合法
    2. 所有 depends_on 引用的 task_id 是否存在
    3. 是否存在循环依赖
    4. 是否存在重复 task_id
    """
    issues = []

    # 收集所有 task_id
    all_ids = set()
    for tier in dag:
        for node in tier:
            tid = node.get("id", "")
            role = node.get("role", "")
            if not tid or not role:
                issues.append(f"任务节点缺少 id 或 role：{node}")
                continue
            if tid in all_ids:
                issues.append(f"重复的 task_id：{tid}")
            all_ids.add(tid)

            if role not in VALID_ROLES:
                issues.append(f"无效角色 '{role}'（task_id={tid}）。合法角色：{sorted(VALID_ROLES)}")

    # 检查 depends_on 引用是否存在
    for tier in dag:
        for node in tier:
            for dep in node.get("depends_on", []):
                if dep not in all_ids:
                    issues.append(f"{node.get('id','?')} 依赖 {dep}，但 {dep} 不在 DAG 中")

    # 检查循环依赖（DFS）
    def _has_cycle(tid, visited, rec_stack):
        visited.add(tid)
        rec_stack.add(tid)
        for tier in dag:
            for node in tier:
                if node.get("id") == tid:
                    for dep in node.get("depends_on", []):
                        if dep not in visited:
                            if _has_cycle(dep, visited, rec_stack):
                                return True
                        elif dep in rec_stack:
                            return True
        rec_stack.discard(tid)
        return False

    visited = set()
    for tid in all_ids:
        if tid not in visited:
            if _has_cycle(tid, visited, set()):
                issues.append(f"检测到循环依赖，涉及：{tid}")
                break  # 报一个就行

    return issues

def _load_default_dag(fallback_task: str) -> list:
    """返回默认的完整开发流程 DAG（委托给 _extract_dag 的 fallback 逻辑，避免重复定义）。"""
    return _extract_dag("", fallback_task)


def _find_completed_tasks_from_snapshots() -> set[str]:
    """扫描快照目录，找出已有快照的 task_id（用于断点续跑）。
    文件名格式: snap_TASK_ID_YYYYMMDD_HHMMSS.json
    注意 task_id 可能含下划线（如 DBG_1, RETEST_2, D_final）。"""
    snap_dir = Path("state/snapshots")
    if not snap_dir.exists():
        return set()
    completed = set()
    for f in snap_dir.glob("snap_*.json"):
        name = f.stem  # 去掉 .json
        parts = name.split("_")
        # 从右往左找日期部分（YYYYMMDD，8位数字），之前的部分即为 task_id
        # snap_DBG_1_20260511_143215 → parts = ["snap","DBG","1","20260511","143215"]
        date_idx = None
        for i in range(len(parts) - 1, 0, -1):
            if len(parts[i]) == 8 and parts[i].isdigit():
                date_idx = i
                break
        if date_idx and date_idx > 1:
            task_id = "_".join(parts[1:date_idx])  # "DBG_1", "T001", "D_final"
            completed.add(task_id)
    return completed


def _format_dag_preview(dag: list[list[dict]]) -> str:
    """把 DAG 格式化为可读的预览文本。"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"PM 规划的任务执行计划")
    lines.append(f"{'='*60}")
    total = sum(len(tier) for tier in dag)
    lines.append(f"共 {len(dag)} 个执行层，{total} 个任务\n")
    for i, tier in enumerate(dag):
        lines.append(f"── 第 {i+1} 层 ──")
        for node in tier:
            role = node["role"]
            task = node["task"][:60] + ("..." if len(node["task"]) > 60 else "")
            deps = node.get("depends_on", [])
            dep = f" [依赖: {', '.join(deps)}]" if deps else ""
            if role == "_approval":
                lines.append(f"  ⏸  [人工审批] {task}")
            else:
                lines.append(f"  →  [{node['id']}] {role.upper()}: {task}{dep}")
        lines.append("")
    lines.append(f"{'='*60}")
    return "\n".join(lines)


async def _request_dag_approval(dag: list[list[dict]]) -> bool:
    """
    展示 DAG 并等待用户确认（两阶段）。
    阶段一：用户确认已看到（无超时）
    阶段二：用户做出决定（3600s 超时）

    CLI 模式：一步完成 input()
    HTTP 模式：两阶段，POST /approve-dag
    """
    preview = _format_dag_preview(dag)
    logger.info(preview)

    # 自动化模式：跳过人工审批
    if AUTO_APPROVE:
        logger.info("  ⏭ AUTO_APPROVE 开启，自动批准 DAG")
        return True

    # HTTP 模式：两阶段轮询
    if not sys.stdin.isatty():
        ack_file = Path("state/_dag_approval_ack.json")
        dec_file = Path("state/_dag_approval_response.json")
        poll = 5

        # 阶段一：等待确认
        logger.info("  ⏳ 请查看 DAG 计划，确认后 POST /approve-dag {\"status\": \"reviewing\"}")
        while True:
            if ack_file.exists():
                try:
                    ack = json.loads(ack_file.read_text(encoding="utf-8"))
                    ack_file.unlink()
                    logger.info(f"  → 已确认：{ack.get('notes', '开始审查')}")
                    break
                except (json.JSONDecodeError, KeyError):
                    ack_file.unlink()
            await asyncio.sleep(poll)

        # 阶段二：计时等待决定
        waited = 0
        max_wait = 3600
        logger.info(f"  ⏱ 计时开始（{max_wait}s 内需做出决定）")
        while waited < max_wait:
            if dec_file.exists():
                try:
                    dec = json.loads(dec_file.read_text(encoding="utf-8"))
                    dec_file.unlink()
                    return dec.get("approved", False)
                except (json.JSONDecodeError, KeyError):
                    dec_file.unlink()
            await asyncio.sleep(poll)
            waited += poll
        logger.warning("  ⏱ DAG 审批超时，自动拒绝")
        return False

    # CLI 模式
    response = input("确认执行以上计划？(y=执行 / n=重新规划) → ").strip().lower()
    if response in ("n", "no"):
        logger.info("  → 已取消，PM 将重新规划")
        return False
    logger.info("  → 开始执行")
    return True


def _tester_found_bugs(tester_result: dict) -> bool:
    """
    检查 Tester 的输出是否指示发现了需要修复的 Bug。

    判断逻辑（多信号交叉验证，避免关键词误判）：
    1. 查找结构化 Bug 条目：匹配 'BUG-001'、'Bug #1'、'缺陷-01' 模式
    2. 查找质量结论：'阻塞发布' / '有条件发布' → 确认有 Bug
       '可发布' → 确认无 Bug
    3. 两项信号交叉验证：只有两种信号一致时才判定
    4. 回退：如果找不到结构化信号，检查是否有失败测试用例列表（TC- 标记为 FAIL）
    """
    if not tester_result or tester_result.get("status") != "done":
        return False

    output = tester_result.get("output") or ""
    summary = tester_result.get("summary") or ""
    full = output + " " + summary

    # 信号1：结构化 Bug 条目（精确匹配，避免误判）
    bug_patterns = [
        r'\bBUG[-_]\d+',           # BUG-001, BUG_001
        r'\bBug\s*#\s*\d+',        # Bug #001
        r'缺陷[-_]\d+',             # 缺陷-01
        r'\bDEFECT[-_]\d+',        # DEFECT-001
    ]
    has_structured_bugs = any(
        re.search(p, full, re.IGNORECASE) for p in bug_patterns
    )

    # 信号2：质量结论
    has_blocking = bool(re.search(r'阻塞发布|block.*release|不能发布|不可发布', full, re.IGNORECASE))
    has_conditional = bool(re.search(r'有条件发布|conditional.*release', full, re.IGNORECASE))
    has_clear = bool(re.search(r'可发布\b|可以发布|ready.*release|cleared.*release', full, re.IGNORECASE))
    bugs_found = has_blocking or has_conditional

    # 两个信号都指向「有Bug」→ 确认
    if has_structured_bugs and bugs_found:
        return True
    # 两个信号都指向「无Bug」→ 确认
    if not has_structured_bugs and not bugs_found and has_clear:
        return False

    # 信号不一致时：有结构化Bug但结论是「可发布」→ 保守处理，视为有Bug
    if has_structured_bugs and has_clear:
        return True

    # 信号3（回退）：检查失败测试用例
    # 匹配 "TC-XXX ... FAIL" 或 "✗ TC-XXX" 模式
    has_failed_tests = bool(re.search(
        r'(TC[-_]\d+).{0,30}(FAIL|失败|✗|❌|不通过)',
        full, re.IGNORECASE
    ))
    if has_failed_tests and not has_clear:
        return True

    # 没有任何明确信号 → 视为无 Bug（避免误触发 QA→DBG 循环）
    return False


async def _request_human_approval(task_node: dict, results: dict) -> dict:
    """
    人工审批节点：暂停执行，等待人工确认。
    两种模式自动切换：
      - CLI 模式（tty）：直接 input() 交互
      - HTTP 模式（非 tty）：两阶段文件轮询（POST /approve）
    """
    task_id = task_node["id"]
    message = task_node.get("task", "请确认是否继续")

    # 收集上游摘要供参考
    upstream_summaries = []
    for dep_id in task_node.get("depends_on", []):
        if dep_id in results and results[dep_id].get("status") == "done":
            upstream_summaries.append(
                f"  [{dep_id}] {results[dep_id].get('summary', '')}"
            )

    logger.info("人工审批: %s — %s", task_id, message)
    logger.info(f"\n{'='*60}")
    logger.info(f"[人工审批节点] {task_id}")
    logger.info(f"问题：{message}")
    if upstream_summaries:
        logger.info(f"上游完成情况：\n" + "\n".join(upstream_summaries))
    logger.info(f"{'='*60}")

    # 自动化模式：跳过人工审批
    if AUTO_APPROVE:
        logger.info(f"  ⏭ AUTO_APPROVE 开启，自动批准 [{task_id}]")
        return {"id": task_id, "role": "_approval", "status": "done",
                "output": "自动批准（AUTO_APPROVE=True）", "summary": "自动批准"}

    # ── HTTP 模式：两阶段文件轮询 ──────────────────
    if not sys.stdin.isatty():
        approval_dir = Path("state")
        ack_file     = approval_dir / "_approval_ack.json"
        decision_file = approval_dir / "_approval_response.json"
        poll = 5

        # 阶段一：等待用户确认已看到（无超时）
        logger.info("  ⏳ 等待你确认已看到审批内容（POST /approve {status: \"reviewing\"}）...")
        while True:
            if ack_file.exists():
                try:
                    ack = json.loads(ack_file.read_text(encoding="utf-8"))
                    ack_file.unlink()
                    logger.info(f"  → 已确认：{ack.get('notes', '开始审查')}")
                    break
                except (json.JSONDecodeError, KeyError):
                    ack_file.unlink()
            await asyncio.sleep(poll)

        # 阶段二：确认后开始计时，等待决定
        max_wait = 3600
        waited = 0
        logger.info(f"  ⏱ 计时开始（{max_wait}s 内需做出决定）")
        while waited < max_wait:
            if decision_file.exists():
                try:
                    decision = json.loads(decision_file.read_text(encoding="utf-8"))
                    decision_file.unlink()
                    approved = decision.get("approved", False)
                    notes = decision.get("notes", "")
                    logger.info(f"  → 审批结果：{'批准' if approved else '拒绝'} — {notes}")
                    break
                except (json.JSONDecodeError, KeyError):
                    decision_file.unlink()
            await asyncio.sleep(poll)
            waited += poll
        else:
            logger.warning(f"  ⏱ [{task_id}] 审批超时（{max_wait}s），自动拒绝")
            approved = False
            notes = "审批超时，自动拒绝"

    # ── CLI 模式：交互式输入 ────────────────────────
    else:
        response = input("批准继续？(y=批准 / n=中止 / s=跳过此检查) → ").strip().lower()
        approved = response in ("y", "yes", "s", "")
        if response == "n":
            logger.info("  → 已中止。可修改后重新运行，或 rollback_to_snap() 回退。")
        notes = input("备注（可选，直接回车跳过）→ ").strip() or ""

    # 更新项目状态
    from state_manager import update_project
    update_project({
        "decisions_log": [{
            "ts": __import__("datetime").datetime.now().isoformat(),
            "decision": f"人工审批 {task_id}：{'批准' if approved else '中止'}",
            "made_by": "Human",
            "notes": notes,
        }]
    }, dispatch_id=task_id)

    status = "done" if approved else "blocked"
    return {
        "id":      task_id,
        "role":    "_approval",
        "status":  status,
        "output":  f"人工审批：{'批准' if approved else '中止'}。备注：{notes}",
        "summary": f"{'批准' if approved else '中止'} — {notes or '无备注'}",
    }

# ── CLI ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from state_manager import init_project

    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "测试任务"
    init_project(f"MA_{task[:20]}")

    async def main():
        result = await run_project(task)
        logger.info("\n" + "═"*60)
        logger.info(result[:2000])

    asyncio.run(main())
