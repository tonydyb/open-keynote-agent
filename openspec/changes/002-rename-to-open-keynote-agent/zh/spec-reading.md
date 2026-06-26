# 002-rename-to-open-keynote-agent 中文阅读版

这份文档是 `002-rename-to-open-keynote-agent` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 的目标是把项目方向从通用的 `open-mac-agent` 调整为更聚焦的 `Open Keynote Agent`。

也就是说，项目不再试图一开始就做“控制所有 macOS app 的通用 agent”，而是先专注于一个明确产品场景：

```text
用自然语言创建、编辑、验证、导出 Apple Keynote 演示文稿。
```

这个 change 只改项目定位和文档，不实现 Keynote 自动化，也不做代码层面的机械重命名。

## 2. 为什么要改方向

通用 macOS agent 范围太大，会同时涉及：

- 多个 app 的行为差异。
- AppleScript、JXA、Accessibility API 等不同自动化方式。
- macOS 权限和 UI 状态。
- 很多难以测试的真实桌面场景。

Keynote 是更适合作为下一阶段的聚焦目标，因为它仍然能覆盖桌面 agent 的核心能力：

- 多轮交互。
- session state。
- planner / executor 分离。
- tool calling。
- 本地 macOS 自动化。
- 修改前确认。
- 导出和验证。

但它的产品边界更窄，更容易逐步做出可用结果。

## 3. 本阶段要做什么

本 change 要更新文档，让读者明确：

- 产品名是 `Open Keynote Agent`。
- 项目 slug 是 `open-keynote-agent`。
- 长期方向是 Keynote 创建和编辑 agent。
- 现有 CLI 文件整理器是已经完成的第一个学习里程碑。
- 后续工作应围绕 interactive session、Keynote tools、observations、export verification 展开。

## 4. 本阶段不做什么

本 change 不做：

- 不实现 Keynote 自动化。
- 不引入 AppleScript / JXA / Accessibility API。
- 不重命名 Python package。
- 不重命名 CLI 命令。
- 不重命名 git repository 目录。
- 不删除已经完成的文件整理器。

换句话说，这一步只是“项目方向校准”，不是实现层改造。

## 5. 现有文件整理器的地位

`oma organize` 和 `oma ask` 仍然保留。

它们代表第一阶段已经搭好的 agent 基础：

- LLM provider 抽象。
- 结构化请求校验。
- 确定性本地工具。
- 修改前确认。
- 运行日志。
- 无云凭证测试。

但是它们不再是长期产品中心。后续产品中心是 Keynote。

## 6. 未来架构方向

文档中应把未来方向写清楚：

```text
interactive session runtime
  -> planner
  -> tool registry
  -> executor
  -> observations
  -> session state
  -> run logs

keynote adapter
  -> AppleScript / JXA first
  -> Accessibility API fallback later
  -> export and verification tools
```

这为后面的 004、005 等 change 铺路。

## 7. 正式需求

### REQ-001：项目名称和用途

文档必须使用 `Open Keynote Agent` 作为产品名，使用 `open-keynote-agent` 作为项目 slug。

读者打开 README 或 OpenSpec 项目概览时，应理解这个项目聚焦 Keynote 演示文稿自动化，而不是通用 macOS 自动化。

### REQ-002：保留文件整理器上下文

文档仍可包含文件整理器命令，但必须说明它是第一阶段 agent foundation，不是长期产品方向。

### REQ-003：本 change 不做机械重命名

本 change 不要求重命名 Python package、CLI command 或 repository directory。

这些重命名留到 change 003 处理。

### REQ-004：未来路线

文档必须指出下一步方向是 interactive Keynote agent，包括 session、Keynote tools、observations 和 export verification。

## 8. 验收标准

完成后应满足：

- README 和 OpenSpec project 文档都表达 Keynote-focused 产品方向。
- 文件整理器被描述为已完成的学习里程碑。
- 文档明确本 change 不改 package / CLI / repo 名称。
- 后续实现方向清楚指向 interactive Keynote agent。

