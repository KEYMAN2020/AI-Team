# 已知坑与解决方案

> 以下为人类整理的种子经验。Agent 自动归档的坑在 auto/gotchas.md。

## 大模型输出格式不稳定

**影响角色**：通用
**日期**：2026-05-12
**来源**：人工总结

**症状**：LLM 输出中 <dag> JSON 格式错误、state_update 解析失败、偶尔不按模板输出

**根因**：非推理模型（temperature=0）输出仍有随机性；推理模型在长上下文下会「遗忘」格式要求

**解决方案**：
1. 关键标签（<dag>、<state_update>）用独立代码块包裹
2. runner 层的 _extract_dag / parse_state_update 永远有 fallback 逻辑
3. 对 JSON 字段做 json.JSONDecodeError 容错

---

## Sub_requests 循环爆炸

**影响角色**：PM, UX, ARCHITECT
**日期**：2026-05-12
**来源**：人工总结

**症状**：Agent A 发 sub_request 给 Agent B，Agent B 再发 sub_request 给 Agent C，
导致 token 消耗剧增、超时

**根因**：sub_request 嵌套调用，没有深度限制

**解决方案**：
1. MAX_SUB_REQUESTS=3 限制单 Agent 发起的 sub_request 数量
2. sub_request 不递归（_handle_sub_requests 不处理 sub agent 输出中的 sub_requests）
3. 如果信息不足，Agent 应在输出中标注「缺少 XXX，建议下游补充」

---

## 工具调用死循环

**影响角色**：FRONTEND, BACKEND, DEVOPS
**日期**：2026-05-12
**来源**：人工总结

**症状**：Agent 在 tool_loop 中反复读取同一文件、循环调用 web_search 相同关键词

**根因**：模型在 tool_use → tool_result 循环中无法收敛，反复要求同一操作

**解决方案**：
1. max_iter=5 硬上限
2. 如果达到上限，最后请求一次不传 tools（让模型输出纯文本）
3. 工具返回结果包含有用信息后，模型应继续文本输出而非重复调用
