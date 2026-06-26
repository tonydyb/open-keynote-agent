# 005-add-keynote-applescript-adapter 中文阅读版

这份文档是 `005-add-keynote-applescript-adapter` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 把 004 中的 interactive runtime 接到真实 Keynote 上。

004 只有 `demo.*` 工具，所有文档和 slide 都存在内存里。005 新增 `keynote.*` 工具，通过 AppleScript 和 `osascript` 控制真实 Keynote。

核心目标：

```text
oka session --tools keynote
  -> ToolRegistry
  -> keynote.* handlers
  -> ScriptRunner
  -> osascript
  -> Apple Keynote
```

同时，普通单元测试不能依赖真实 Keynote、`osascript` 或 macOS Automation 权限。

## 2. 新增抽象：ScriptRunner

本 change 新增一个窄接口：

```python
class ScriptRunner(Protocol):
    def run(self, script: str) -> ScriptRunResult: ...
```

返回结构：

```text
ScriptRunResult:
  stdout: str
  stderr: str
  returncode: int
  ok: bool
```

生产环境使用：

```text
OsascriptRunner
  -> subprocess.run(["osascript", "-e", script])
```

测试环境使用：

```text
FakeScriptRunner
  -> 返回预设 ScriptRunResult
  -> 记录 calls
```

这样 Keynote tool handler 可以被完整测试，而不真正启动 Keynote。

## 3. 新增模块

```text
src/open_keynote_agent/
  applescript/
    __init__.py
    runner.py      # ScriptRunner, OsascriptRunner, FakeScriptRunner
    scripts.py     # AppleScript builders

  tools/
    keynote.py     # keynote.* handlers + register_keynote_tools()
```

004 的 planner、executor、registry 不需要改。

## 4. AppleScript builders

`scripts.py` 负责生成 AppleScript 字符串。

每个 builder 返回一个可以传给 `osascript -e` 的完整脚本。

核心 builders：

| 函数 | 作用 |
|---|---|
| `applescript_string(value)` | 转义用户字符串 |
| `create_document(name)` | 创建新 Keynote document |
| `add_slide(master_name)` | 用指定 master slide 添加 slide |
| `set_slide_title(slide, title)` | 设置 slide 标题 |
| `set_slide_body(slide, body)` | 设置 slide 正文 |
| `export_pdf(posix_path)` | 导出 PDF |
| `get_document_info()` | 返回 document name 和 slide count |

重要规则：

- 所有用户可控字符串必须经过 `applescript_string`。
- 不允许把未转义字符串直接插入 AppleScript。
- 脚本不能包含 `display dialog` 这类阻塞 UI。
- 路径统一使用 POSIX path，在 AppleScript 边界转换。

## 5. Keynote tools

新增这些工具：

| Tool | 参数 | 是否修改状态 |
|---|---|---|
| `keynote.create_document` | `name: str` | yes |
| `keynote.add_slide` | `layout: str` | yes |
| `keynote.set_slide_title` | `slide: int`, `title: str` | yes |
| `keynote.set_slide_body` | `slide: int`, `body: str` | yes |
| `keynote.export_pdf` | `path: str` | yes |
| `keynote.get_document_info` | none | no |

每个 handler 是一个 closure，持有 `ScriptRunner`：

```python
def _make_create_document(runner):
    def handler(args, context):
        script = scripts.create_document(...)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        ...
    return handler
```

executor 会捕获异常并记录为 `ToolResult(ok=False)`。

## 6. context["keynote"]

Keynote tools 会维护一个轻量本地状态：

```text
context["keynote"]:
  name: str
  slide_count: int
```

这是 best-effort mirror。真实状态以 Keynote 本身为准，`keynote.get_document_info` 可以重新从 Keynote 读取并更新 context。

## 7. add_slide 的第一版 layout

005 的第一版只支持简单语义 layout：

```text
title
title_body
blank
```

映射到当时测试过的 Keynote master name：

| layout | master name |
|---|---|
| `title` | `Title` |
| `title_body` | `Title & Bullets` |
| `blank` | `Blank` |

注意：后续 006 会把这套固定映射升级为 theme/layout discovery。

## 8. export_pdf 安全要求

`keynote.export_pdf` 必须按顺序做：

1. 展开并 resolve path。
2. 检查 parent directory 存在。
3. 检查目标 PDF 不存在。
4. 前三步通过后才调用 AppleScript。

如果目标文件已存在，必须在调用 `osascript` 前失败，不能覆盖。

本 change 不支持 `overwrite=True`。

## 9. CLI 集成

004 的 `oka session` 默认注册 demo tools。

005 增加 `--tools` 选项：

```bash
oka session                   # 默认 demo tools
oka session --tools demo      # 显式 demo tools
oka session --tools keynote   # 使用真实 Keynote tools
```

当使用 Keynote tools 时，启动前打印提示：

```text
Note: macOS may prompt for permission to control Keynote via Automation.
```

## 10. 测试策略

普通单元测试：

- 使用 `FakeScriptRunner`。
- 不调用真实 `osascript`。
- 不启动 Keynote。
- 不需要 macOS Automation 权限。

`OsascriptRunner` 的测试通过 monkeypatch `subprocess.run` 完成。

真实 Keynote integration test：

- 标记为 `pytest.mark.keynote_integration`。
- 默认跳过。
- 只有设置 `RUN_KEYNOTE_INTEGRATION=1` 才运行。

smoke test 流程：

```text
create document
-> add slide
-> set title
-> export PDF
-> assert PDF exists
```

## 11. 本阶段不做什么

本 change 不做：

- 不使用 Accessibility API。
- 不支持 JXA。
- 不做复杂布局选择。
- 不插入图片。
- 不做主题系统。
- 不做动画。
- 不修改 004 runtime 核心语义。
- 不删除 demo tools。

## 12. 验收标准

完成后应满足：

- `keynote.*` tools 能注册到 ToolRegistry。
- `oka session --tools keynote` 可启动。
- 单元测试全部使用 fake runner，稳定通过。
- ruff 通过。
- macOS + Keynote 环境下，opt-in integration smoke test 能创建文档、添加 slide、导出 PDF。

