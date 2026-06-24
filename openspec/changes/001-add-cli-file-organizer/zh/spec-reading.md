# 001-add-cli-file-organizer 中文阅读版

这份文档是 `001-add-cli-file-organizer` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 要为 `open-mac-agent` 增加第一个可运行的 CLI agent 工作流：文件夹整理 agent。

用户可以通过命令行请求 agent 整理某个本地文件夹。系统会扫描文件、按类型生成移动计划、展示 dry-run 预览，并在用户确认后执行移动操作。每次运行都需要保存可审计日志。

第一阶段重点不是 macOS GUI 自动化，而是先搭出 agent 的基本骨架：

- 理解用户意图。
- 生成结构化计划。
- 调用确定性的本地工具。
- 展示执行前预览。
- 对真实文件移动要求用户确认。
- 执行后输出报告。
- 保存运行日志，方便复盘和调试。

这个基础以后会复用到 Finder、Keynote、Numbers 等 macOS app adapter。

## 2. 项目原则

`open-mac-agent` 第一阶段遵循这些原则：

- 执行动作优先使用确定性的本地工具。
- 大语言模型只负责意图解析、规划和解释，不直接执行未检查的系统修改。
- 移动、删除、覆盖、发送等风险操作必须显式确认。
- 所有会修改系统状态的工作流都必须支持 dry-run。
- 每次运行都要记录足够的信息，方便调试、回放和审计。
- 不同模型供应商必须隔离在窄接口 adapter 后面。

## 3. 范围

本阶段要做：

- Python CLI 包。
- 文件夹整理工作流。
- 可插拔 LLM adapter。
- 本地文件系统工具。
- 执行日志。
- 自动化测试。

本阶段不做：

- macOS GUI 自动化。
- Accessibility API 集成。
- 长时间后台自主 agent。
- 浏览器控制。
- 远程文件操作。
- 删除文件。
- 覆盖已有文件。

## 4. 用户故事

- 作为学习者，我可以运行 `oma organize ./demo --dry-run`，看到文件会被移动到哪里。
- 作为学习者，我可以运行 `oma organize ./demo --apply`，确认后执行安全的移动计划。
- 作为用户，我可以运行 `oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"`，让模型把自然语言转换成结构化整理请求。
- 作为开发者，我可以查看 `.runs/<run-id>/`，理解 agent 当时计划了什么、调用了什么、执行了什么。
- 作为开发者，我可以在没有云凭证或 API key 的情况下运行测试。

## 5. CLI 设计

CLI 入口命令叫 `oma`。

必须支持这些命令：

```bash
oma organize ./demo --dry-run
oma organize ./demo --apply
oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"
```

`oma organize` 是确定性命令，不需要大语言模型。

`oma ask` 使用大语言模型把自然语言转换成经过校验的结构化请求。自然语言命令默认是 dry-run，除非用户明确要求 apply，并且在执行前再次确认。

## 6. 文件分类规则

第一版使用文件扩展名分类，只处理目标目录下一层的普通文件，不递归处理子目录。

初始分类：

```text
PDFs: .pdf
Images: .jpg, .jpeg, .png, .gif, .webp, .heic, .tiff, .bmp, .svg
Documents: .doc, .docx, .txt, .md, .rtf, .pages
Spreadsheets: .xls, .xlsx, .csv, .tsv, .numbers
Presentations: .ppt, .pptx, .key
Archives: .zip, .tar, .gz, .tgz, .rar, .7z
Audio: .mp3, .wav, .m4a, .flac, .aac
Video: .mp4, .mov, .mkv, .avi, .webm
Code: .py, .js, .ts, .tsx, .jsx, .java, .go, .rs, .rb, .php, .html, .css, .json, .yaml, .yml, .toml
Others: 其他所有文件
```

## 7. 计划模型

实现时应使用类型化数据结构表示请求和计划。

示例结构：

```python
class OrganizeRequest(BaseModel):
    target_dir: Path
    categories: list[str] | None = None
    dry_run: bool = True

class MoveOperation(BaseModel):
    source: Path
    destination: Path
    category: str

class OrganizePlan(BaseModel):
    target_dir: Path
    operations: list[MoveOperation]
    skipped: list[SkippedFile]
```

路径校验必须确保所有移动操作都限制在目标目录内，不能通过路径穿越操作到外部目录。

## 8. LLM Provider 设计

LLM 层必须使用 provider-neutral 接口。

示例接口：

```python
class LLMClient(Protocol):
    def complete_json(self, messages: list[dict], schema: dict) -> dict:
        ...
```

需要支持这些 provider：

- `BedrockConverseClient`：AWS Bedrock。
- `OpenAIClient`：用户自己的 OpenAI API key。
- `GeminiClient`：用户自己的 Gemini API key。
- `FakeLLMClient`：测试使用，不访问网络。

agent 其他部分不能依赖 provider SDK 的具体对象。所有 provider 都应该暴露相同的 `complete_json` 行为。

配置项：

```text
OMA_LLM_PROVIDER=bedrock|openai|gemini|fake

# Bedrock
AWS_PROFILE
AWS_REGION
BEDROCK_MODEL_ID

# OpenAI
OPENAI_API_KEY
OPENAI_MODEL

# Gemini
GEMINI_API_KEY
GEMINI_MODEL
```

provider SDK 应尽量使用可选依赖或延迟导入，这样用户即使没有配置全部 provider，也可以运行确定性的 CLI 功能。自动化测试必须使用 `FakeLLMClient`，不得访问外部 LLM 服务。

## 9. 安全要求

agent 必须满足：

- `oma ask` 默认 dry-run。
- 文件系统修改前必须要求用户确认。
- 拒绝覆盖已有目标文件。
- 拒绝目标目录外的路径操作。
- 拒绝不存在的目标目录。
- 拒绝非目录类型的目标路径。
- 本 change 中永远不删除文件。

如果目标文件已存在，该移动操作应跳过并记录原因。未来可以通过新的 change 增加自动重命名策略。

## 10. 运行日志

每次运行都应创建：

```text
.runs/
  <timestamp>-<short-id>/
    request.json
    plan.json
    tool_calls.jsonl
    result.json
```

日志需要回答这些问题：

- 用户请求是什么？
- agent 生成了什么计划？
- 调用了哪些工具？
- 实际修改了什么？
- 哪些文件被跳过，原因是什么？

## 11. 正式需求

### REQ-001：确定性 organize 命令

系统必须提供一个不依赖 LLM 的 CLI 命令，按类型整理目标目录中的文件。

场景：预览文件整理

- 给定目录里有 `report.pdf`、`photo.png` 和 `notes.md`。
- 当用户运行 `oma organize <directory> --dry-run`。
- 系统应显示移动计划。
- `report.pdf` 应计划移动到 `PDFs/report.pdf`。
- `photo.png` 应计划移动到 `Images/photo.png`。
- `notes.md` 应计划移动到 `Documents/notes.md`。
- 不应实际移动任何文件。

场景：执行文件整理

- 给定目录里有 `report.pdf`。
- 当用户运行 `oma organize <directory> --apply`。
- 并且用户确认移动计划。
- 系统应按需创建 `PDFs` 分类目录。
- 并将 `report.pdf` 移动到 `PDFs/report.pdf`。

### REQ-002：自然语言 organize 命令

系统必须提供一个 CLI 命令，把自然语言请求转换成经过校验的文件整理请求。

场景：请求整理文件夹

- 给定 Bedrock、OpenAI 或 Gemini 中的某个 LLM provider 已配置。
- 当用户运行 `oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"`。
- 系统应请求已配置的 LLM 生成结构化请求。
- 系统应校验结构化请求。
- 系统应展示移动计划。

场景：自然语言命令默认 dry-run

- 给定目录中有待整理文件。
- 当用户运行 `oma ask "帮我整理 ./demo"`。
- 系统应默认 dry-run。
- 除非用户明确请求 apply 并确认，否则不移动文件。

### REQ-003：修改前确认

系统必须在移动文件前要求用户显式确认。

场景：用户拒绝确认

- 给定已有移动计划。
- 当系统请求确认。
- 用户拒绝或没有确认。
- 系统不得移动任何文件。
- 运行结果应记录执行已取消。

### REQ-004：不覆盖已有文件

系统绝不能覆盖已有目标文件。

场景：目标文件已存在

- 给定目标目录中存在 `report.pdf`。
- 并且 `PDFs/report.pdf` 已经存在。
- 当系统构建或执行移动计划。
- `report.pdf` 对应操作应被跳过。
- 跳过原因应说明目标文件冲突。

### REQ-005：路径安全

系统必须阻止路径穿越和目标目录外的操作。

场景：不安全目标路径

- 给定某个生成的操作目标路径位于目标目录外。
- 当系统校验计划。
- 系统应拒绝该操作。
- 不得发生任何文件系统修改。

### REQ-006：运行日志

系统必须为每次 CLI 执行写入运行产物。

场景：创建运行日志

- 当用户运行 organize 或 ask 命令。
- 系统应创建 `.runs/<run-id>/` 目录。
- 系统应写入 `request.json`。
- 如果生成了计划，系统应写入 `plan.json`。
- 如果调用了工具，系统应写入 `tool_calls.jsonl`。
- 执行结束时，系统应写入 `result.json`。

### REQ-007：无云凭证测试

系统必须支持在没有云凭证、API key 或网络访问的情况下运行自动化测试。

场景：使用 Fake LLM client

- 给定正在运行自动化测试。
- 当测试自然语言规划行为。
- 测试应使用 fake LLM client。
- 测试不得调用 Bedrock、OpenAI 或 Gemini。

### REQ-008：可选择 LLM provider

系统必须允许用户选择 AWS Bedrock、OpenAI API、Gemini API，或测试用 fake provider。

场景：使用 Bedrock provider

- 给定 `OMA_LLM_PROVIDER` 设置为 `bedrock`。
- 并且 Bedrock 配置存在。
- 当用户运行 `oma ask "<request>"`。
- 系统应使用 Bedrock adapter。

场景：使用 OpenAI provider

- 给定 `OMA_LLM_PROVIDER` 设置为 `openai`。
- 并且 `OPENAI_API_KEY` 存在。
- 当用户运行 `oma ask "<request>"`。
- 系统应使用 OpenAI adapter。

场景：使用 Gemini provider

- 给定 `OMA_LLM_PROVIDER` 设置为 `gemini`。
- 并且 `GEMINI_API_KEY` 存在。
- 当用户运行 `oma ask "<request>"`。
- 系统应使用 Gemini adapter。

场景：provider 配置缺失

- 给定 `OMA_LLM_PROVIDER` 设置为某个 provider，但缺少所需凭证。
- 当用户运行 `oma ask "<request>"`。
- 系统应输出清晰的配置错误。
- 不得发生任何文件系统修改。

## 12. 实现任务清单

### 1. 项目初始化

- [ ] 初始化 `pyproject.toml`。
- [ ] 添加 CLI 入口 `oma`。
- [ ] 添加运行依赖：`typer`、`rich`、`pydantic`、`python-dotenv`。
- [ ] 添加 Bedrock、OpenAI、Gemini 的可选 LLM provider 依赖。
- [ ] 添加开发依赖：`pytest`、`ruff`。
- [ ] 添加 `.env.example`，包含可配置的 LLM provider 变量。
- [ ] 添加初始 `README.md` 快速开始说明。

### 2. 确定性文件整理器

- [ ] 实现基于扩展名的文件分类映射。
- [ ] 实现 `classify_file(path)` 并添加测试。
- [ ] 实现 `scan_folder(target_dir)`，只扫描一层普通文件。
- [ ] 实现 `build_organize_plan(target_dir, categories=None)`。
- [ ] 确保目标路径在目标目录内。
- [ ] 确保已有目标文件会被跳过。
- [ ] 添加分类和计划生成测试。

### 3. CLI 命令

- [ ] 实现 `oma organize <folder> --dry-run`。
- [ ] 实现 `oma organize <folder> --apply`。
- [ ] 使用 `rich` 渲染可读的移动预览。
- [ ] 在执行移动前请求确认。
- [ ] 确认默认值为 no。
- [ ] 添加 dry-run 和 apply 行为测试。

### 4. 文件系统执行

- [ ] 实现 `move_files(plan)`，作为唯一会修改文件系统的操作。
- [ ] 确保 `move_files` 永远不覆盖文件。
- [ ] 在结果中记录已移动和已跳过文件。
- [ ] 添加冲突处理测试。

### 5. 运行日志

- [ ] 在 `.runs/<run-id>/` 下创建运行会话。
- [ ] 写入 `request.json`。
- [ ] 写入 `plan.json`。
- [ ] 追加工具调用到 `tool_calls.jsonl`。
- [ ] 写入 `result.json`。
- [ ] 添加日志创建测试或 smoke check。

### 6. LLM 抽象

- [ ] 定义 provider-neutral 的 `LLMClient` 协议。
- [ ] 通过 `OMA_LLM_PROVIDER` 选择 provider。
- [ ] 实现测试用 `FakeLLMClient`。
- [ ] 实现自然语言请求 schema 校验。
- [ ] 对格式错误或不支持的 LLM 计划给出清晰错误。
- [ ] 使用 `FakeLLMClient` 添加测试。

### 7. LLM Provider Adapter

- [ ] 使用 `boto3` Bedrock Runtime 实现 `BedrockConverseClient`。
- [ ] 支持配置 `AWS_PROFILE`、`AWS_REGION` 和 `BEDROCK_MODEL_ID`。
- [ ] 使用用户提供的 `OPENAI_API_KEY` 实现 `OpenAIClient`。
- [ ] 支持配置 `OPENAI_MODEL`。
- [ ] 使用用户提供的 `GEMINI_API_KEY` 实现 `GeminiClient`。
- [ ] 支持配置 `GEMINI_MODEL`。
- [ ] 从环境变量加载 provider 配置。
- [ ] 添加一个简洁的 system prompt，要求只返回经过校验的 JSON。
- [ ] 添加 Bedrock、OpenAI、Gemini 的开发配置文档。

### 8. 自然语言 Agent 命令

- [ ] 实现 `oma ask "<request>"`。
- [ ] 将用户文本转换成结构化整理请求。
- [ ] 校验目标文件夹存在。
- [ ] 构建并展示移动计划。
- [ ] 默认 dry-run。
- [ ] 执行前要求显式确认。

### 9. 质量门槛

- [ ] 运行 `ruff check`。
- [ ] 运行 `pytest`。
- [ ] 确认测试不需要云凭证或 API key。
- [ ] 确认 dry-run 不修改文件。
- [ ] 确认 apply 模式不会覆盖已有文件。
- [ ] 更新 README，加入示例和安全说明。

## 13. 验收标准

- `oma organize <folder> --dry-run` 能输出可读的移动预览。
- `oma organize <folder> --apply` 会在移动文件前请求确认。
- `oma ask "<natural language request>"` 可以使用配置好的 LLM provider 生成整理计划。
- 测试不需要网络、云凭证或 API key。
- 每次运行都会在 `.runs/` 下写入请求、计划、工具调用和结果。
