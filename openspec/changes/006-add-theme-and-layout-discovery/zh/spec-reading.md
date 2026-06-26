# 006-add-theme-and-layout-discovery 中文阅读版

这份文档是 `006-add-theme-and-layout-discovery` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 在 005 的 Keynote AppleScript adapter 上增加 theme 和 layout discovery 能力。

005 已经能控制 Keynote，但它把语义 layout 固定映射到少数 Keynote master name，例如：

```text
title_body -> Title & Bullets
```

这个做法在不同 Keynote theme、不同系统版本、不同用户机器上不够稳。006 的目标是让 adapter 在运行时发现：

- 当前机器有哪些 Keynote theme。
- 当前 document 有哪些 slide layout。
- 语义 layout 应该映射到哪个真实 layout name。

这样开源用户下载项目后，可以尽量使用 Mac 自带主题生成类似效果，而不需要安装自定义主题。

## 2. 核心流程

目标使用方式：

```text
oka session --tools keynote
  -> keynote.list_themes
  -> keynote.create_document(theme="Parchment")
  -> keynote.list_layouts
  -> keynote.resolve_layout(layout="title_body")
  -> keynote.add_slide(layout="title_body")
```

`Parchment` 是推荐的内置 storybook-like theme。

## 3. 本阶段要做什么

新增或修改这些工具：

| Tool | 参数 | 是否修改状态 | 作用 |
|---|---|---|---|
| `keynote.list_themes` | none | no | 列出已安装 Keynote themes |
| `keynote.create_document` | `name`, `theme?` | yes | 可选使用指定 theme 创建 document |
| `keynote.list_layouts` | none | no | 列出 front document 的 slide layouts |
| `keynote.resolve_layout` | `layout` | no | 把语义 layout 解析成真实 layout |
| `keynote.add_slide` | `layout` | yes | 使用解析后的真实 layout 添加 slide |

现有工具继续保留：

- `keynote.set_slide_title`
- `keynote.set_slide_body`
- `keynote.export_pdf`
- `keynote.get_document_info`

## 4. Theme Discovery

新增 AppleScript builder：

```python
def list_themes() -> str: ...
```

它必须返回 newline-delimited text：

```text
Basic White
Parchment
Craft
...
```

重点：不能直接返回 AppleScript list。

因为 `osascript` 打印 AppleScript list 时通常会变成逗号分隔：

```text
Basic White, Parchment, Craft
```

而逗号分割不安全，layout 名本身可能包含逗号。

所以 AppleScript 必须使用：

```applescript
set oldDelimiters to AppleScript's text item delimiters
set AppleScript's text item delimiters to "\n"
set output to (name of every theme) as text
set AppleScript's text item delimiters to oldDelimiters
return output
```

handler 解析后返回：

```json
{
  "themes": ["Basic White", "Parchment", "Craft"]
}
```

并写入：

```text
context["keynote"]["themes"]
```

## 5. 使用 theme 创建 document

扩展：

```python
scripts.create_document(name: str, theme: str | None = None)
```

规则：

- `theme is None` 时保持 005 的默认行为。
- `theme` 有值时使用：

```applescript
make new document with properties {document theme:theme "<escaped theme>"}
```

`theme` 必须经过 `applescript_string` 转义。

`name` 仍然只是 session metadata，不写入 AppleScript document properties。原因是 Keynote document name 是 read-only，这个约束在 005 已经确认过。

创建成功后可以记录：

```json
context["keynote"] = {
  "name": "three-pigs",
  "theme": "Parchment",
  "slide_count": 1
}
```

但 `slide_count: 1` 只是 best-effort。真实 slide 数量以 `keynote.get_document_info` 为准。

## 6. Layout Discovery

新增 AppleScript builder：

```python
def list_layouts() -> str: ...
```

它检查 `front document` 的 master slides，并返回 newline-delimited layout names：

```text
Title
Title & Bullets
Title, Content
Blank
...
```

同样必须用 `AppleScript's text item delimiters` 强制换行输出：

```applescript
set oldDelimiters to AppleScript's text item delimiters
set AppleScript's text item delimiters to "\n"
set output to (name of every master slide of front document) as text
set AppleScript's text item delimiters to oldDelimiters
return output
```

禁止用 comma split，因为真实 layout 名可能包含逗号。

handler 写入：

```text
context["keynote"]["layouts"]
```

## 7. Layout Resolver

新增模块：

```text
src/open_keynote_agent/applescript/layout.py
```

这个模块负责：

```python
def _parse_newline_list(text: str) -> list[str]: ...

LAYOUT_CANDIDATES = {
    "title": ["Title", "Title Slide", "Title Only"],
    "title_body": ["Title & Bullets", "Title, Content", "Title and Bullets"],
    "blank": ["Blank"],
}

def resolve_layout_name(semantic: str, available: list[str]) -> str: ...
```

`scripts.py` 只负责 AppleScript builder，不放 layout resolution 逻辑。

`tools/keynote.py` 应从 `applescript/layout.py` import resolver。

005 中旧的 `_LAYOUT_MAP` 必须删除，不能同时保留两套映射表。

## 8. 解析规则

`resolve_layout_name(semantic, available)` 的规则：

1. 如果用户传入的 layout 已经是真实 layout name，并且在 `available` 中，直接返回它。
2. 如果传入的是语义 key，比如 `title_body`，按候选列表顺序找第一个存在的真实 layout。
3. 如果找不到，抛出清晰错误，错误里包含 requested layout 和 available layout names。

## 9. keynote.resolve_layout

新增非修改工具：

```text
keynote.resolve_layout
```

输入：

```json
{
  "layout": "title_body"
}
```

输出：

```json
{
  "layout": "title_body",
  "resolved": "Title & Bullets"
}
```

如果 `context["keynote"]["layouts"]` 已经存在，就直接使用。

如果 context 中没有 layouts，工具必须先调用 `list_layouts` 的 AppleScript、解析结果、更新 context，再执行 resolve。

这样可以避免用户看到 `available choices: []` 这种没帮助的错误。

## 10. 更新 keynote.add_slide

`keynote.add_slide` 不再使用固定 `_LAYOUT_MAP`。

新流程：

1. 读取 `context["keynote"]["layouts"]`。
2. 如果已经有 layouts，不得再调用 `list_layouts`。
3. 如果没有 layouts，调用 `list_layouts` 并更新 context。
4. 调用 `resolve_layout_name`。
5. 用解析后的真实 layout name 构造 `scripts.add_slide(...)`。
6. 执行 AppleScript。

这样用户仍然可以说：

```text
layout=title_body
```

但系统会根据当前 document 的真实 layout 名决定用哪个 master slide。

## 11. 推荐主题

storybook deck 的推荐内置主题是：

```text
Parchment
```

后续 renderer 可以使用 fallback：

```text
Parchment -> Craft -> Basic White
```

本 change 只提供发现和创建能力，不实现完整 storybook renderer。

## 12. Integration smoke test

真实 Keynote 测试仍然默认跳过，只在设置环境变量时运行：

```bash
RUN_KEYNOTE_INTEGRATION=1
```

smoke test 应：

1. 调用 `keynote.list_themes`。
2. 如果有 `Parchment`，选择它。
3. 否则如果有 `Basic White`，选择它。
4. 否则选择返回的第一个 theme。
5. 用选中的 theme 创建 document。
6. 调用 `keynote.list_layouts`。
7. 通过 semantic resolution 添加 `title_body` slide。
8. 导出 PDF。

## 13. 本阶段不做什么

本 change 不做：

- 不实现完整 storybook renderer。
- 不插入图片。
- 不新增 object-level text box 或 shape tools。
- 不要求用户安装自定义 theme。
- 不引入 GUI automation 或 Accessibility API。
- 不让真实 Keynote integration tests 默认运行。

## 14. 测试要求

单元测试必须使用 `FakeScriptRunner`。

需要覆盖：

- `scripts.list_themes()` 使用 newline delimiter。
- `scripts.list_layouts()` 使用 newline delimiter。
- `_parse_newline_list` 保留包含逗号的 layout name。
- theme-based `create_document`。
- `resolve_layout_name` exact match。
- `resolve_layout_name` semantic match。
- unknown layout error。
- `keynote.resolve_layout` 使用缓存 layouts。
- `keynote.resolve_layout` 在缺少 layouts 时自动 fetch。
- `keynote.add_slide` 在已有 layouts 时不调用 list_layouts。
- `keynote.add_slide` 在缺少 layouts 时调用 list_layouts。

普通测试不得调用真实 `osascript`，不得要求 Keynote 或 macOS Automation 权限。

## 15. 验收标准

完成后应满足：

- 现有测试继续通过。
- 新增单元测试覆盖 theme listing、layout listing、theme create 和 semantic layout resolution。
- `keynote.create_document` 支持可选 `theme`。
- `keynote.add_slide layout=title_body` 可基于当前 document 的 discovered layouts 工作。
- `Parchment` 被记录为推荐内置 storybook theme。
- 真实 Keynote integration test 仍然 opt-in。

