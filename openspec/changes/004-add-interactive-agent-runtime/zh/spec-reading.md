# 004-add-interactive-agent-runtime 中文阅读版

这份文档是 `004-add-interactive-agent-runtime` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 为 `open-keynote-agent` 增加一个多轮交互式 agent runtime：

```bash
uv run oka session
```

用户可以在 REPL 中一轮一轮输入自然语言。agent 会：

1. 根据用户输入生成工具调用计划。
2. 展示计划。
3. 等待用户确认。
4. 执行已确认的工具。
5. 把结果写回 session state。
6. 记录结构化 event log。

本 change 不做真实 Keynote 自动化。它先搭好 runtime，让后续 `keynote.*` tools 可以插进来。

## 2. 为什么需要 runtime

原来的 `oka organize` 和 `oka ask` 是一次性命令：

```text
输入一次 -> 生成计划 -> 执行或 dry-run -> 退出
```

Keynote agent 需要的是多轮、上下文连续的 workflow：

```text
user> create a keynote deck named demo
agent> Plan: demo.create_document name=demo
Apply? [y/N]

user> add a title slide
agent> Plan: demo.add_slide ...
Apply? [y/N]

user> export it as PDF
agent> Plan: demo.export_pdf ...
Apply? [y/N]
```

所以必须先有 session state、planner、executor、tool registry、observations 和 event log。

## 3. 核心数据流

每一轮的流程是：

```text
user instruction
  -> planner (LLM + tool registry)
  -> proposed tool calls
  -> confirmation prompt
  -> executor (tool registry)
  -> tool results
  -> observations added to session state
  -> event appended to session log
```

这里的重点是：LLM 只输出结构化工具调用计划，真正执行由本地 executor 和已注册工具完成。

## 4. 新增模块

本 change 新增这些模块：

```text
src/open_keynote_agent/
  agent/
    session.py       # SessionState, Turn
    planner.py       # Plan, ProposedToolCall, plan_turn()
    executor.py      # execute_plan(), ToolResult
    registry.py      # ToolRegistry, ToolDefinition

  runtime/
    events.py        # SessionEvent, event types

  tools/
    demo.py          # demo.* tools
```

`demo.*` tools 模拟 Keynote-like workflow，但不控制真实 Keynote。

## 5. SessionState

`SessionState` 是一个 session 内的共享状态：

```text
SessionState:
  session_id: str
  turns: list[Turn]
  context: dict
```

`context` 是工具之间共享状态的地方。例如 demo tools 会把文档名和 slides 放到：

```text
context["demo"]
```

未来 Keynote tools 会使用：

```text
context["keynote"]
```

## 6. Planner

Planner 的职责是：

- 读取用户 instruction。
- 读取当前 session state 的最近 observations。
- 读取 tool registry 中的工具描述和参数 schema。
- 调用 LLM 的 `complete_json(...)`。
- 校验 LLM 返回的 `Plan`。

`Plan` 结构：

```text
Plan:
  steps: list[ProposedToolCall]

ProposedToolCall:
  tool: str
  args: dict
  description: str
```

Planner 必须在展示给用户之前校验：

- 工具名必须存在。
- 必填参数必须存在。
- 参数必须符合工具 schema。

校验失败时抛出 `PlanValidationError`。

## 7. Tool Registry

`ToolRegistry` 是工具注册表：

```text
ToolDefinition:
  name: str
  description: str
  parameters: dict
  mutating: bool
  handler: Callable
```

设计原则：

- CLI 不硬编码工具。
- planner 和 executor 使用同一份 registry。
- 后续新增 Keynote 工具只需要注册 `ToolDefinition`。

## 8. Executor

Executor 的职责是执行已批准的计划：

```text
execute_plan(plan, registry, session_state) -> list[ToolResult]
```

执行规则：

- 按顺序执行工具。
- 每一步执行前再次校验参数。
- handler 成功时记录 `ok=True`。
- handler 抛异常时记录 `ok=False`，并停止当前 plan 后续步骤。
- 每个结果生成 observation，追加到 session state。

`ToolResult` 结构：

```text
ToolResult:
  tool: str
  args: dict
  ok: bool
  output: dict
  error: str | None
  observation: str
```

## 9. Event Log

每个 session 写入：

```text
.runs/<session-id>/events.jsonl
```

每行是一个 JSON event：

```text
SessionEvent:
  seq: int
  type: str
  ts: str
  payload: dict
```

重要事件包括：

- `session_start`
- `turn_start`
- `plan_proposed`
- `plan_approved`
- `plan_rejected`
- `tool_called`
- `tool_result`
- `session_end`

这个 event log 是未来 Studio UI 或 SSE stream 的基础。

## 10. Demo Tools

本 change 提供 `demo.*` tools：

| Tool | 作用 |
|---|---|
| `demo.create_document` | 在 context 中创建模拟文档 |
| `demo.add_slide` | 添加模拟 slide |
| `demo.set_text` | 设置 slide 文本 |
| `demo.export_pdf` | 写一个 placeholder PDF |
| `demo.get_document_info` | 返回模拟文档信息 |

这些工具让 runtime 可以端到端测试，而不依赖 Keynote。

## 11. CLI 行为

用户运行：

```bash
uv run oka session
```

REPL 流程：

1. 显示 `oka>` prompt。
2. 读取用户输入。
3. 调用 planner。
4. 展示 plan。
5. 提示 `Apply? [y/N]`。
6. 用户确认后执行。
7. 展示 observations。
8. 输入 `done`、`exit`、`quit` 或 EOF 后退出。

`--no-confirm` 可以跳过确认，主要用于测试和脚本。

## 12. 安全要求

- 所有 `mutating=True` 的工具都必须确认后执行。
- executor 必须在调用 handler 前校验参数。
- planner 必须拒绝不存在的工具名。
- 错误必须记录成 `ToolResult(ok=False)`，不能静默吞掉。

## 13. 本阶段不做什么

本 change 不做：

- 不控制真实 Keynote。
- 不引入 AppleScript / JXA / Accessibility API。
- 不做 HTTP server。
- 不做 SSE endpoint。
- 不做无需用户确认的自主多步 agent loop。
- 不删除 `oka organize` 和 `oka ask`。

## 14. 验收标准

完成后应满足：

- `oka session` 可以启动 REPL。
- 每轮用户输入可以生成至少一个 proposed tool call。
- 用户可以批准或拒绝 plan。
- 批准后 executor 执行工具并记录 observation。
- `.runs/<session-id>/events.jsonl` 记录完整事件。
- 测试使用 `FakeLLMClient` 和 demo tools，不需要云凭证或 Keynote。

