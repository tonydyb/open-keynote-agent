# 009-add-storybook-renderer 中文阅读版

这份文档是 `009-add-storybook-renderer` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

009 要把 008 生成的 `DeckSpec` 真正渲染成 Keynote。

数据流是：

```text
deck_spec.json
  -> DeckSpec 校验
  -> storybook renderer
  -> keynote.* tools
  -> Keynote 文档
  -> PDF
```

这会成为第一个从“结构化计划”到“真实 Keynote 输出”的完整路径。

## 2. 和前面几个 spec 的关系

006 提供：

- list themes
- create document with theme
- list layouts
- resolve layout names

007 提供：

- add text box
- add emoji text
- add rectangle shape
- move object
- resize object

008 提供：

- 用户长 prompt -> DeckSpec JSON
- slide outline
- DeckSpec 结构校验

009 消费 008 的 DeckSpec，然后调用 006/007 的工具渲染。

## 3. 重要边界

009 不是 LLM planner。

它不调用 LLM，也不让 LLM 决定坐标。

009 使用确定性童话绘本模板，把 DeckSpec 转成一组固定规则的 Keynote 工具调用。

本 change 不做：

- 图片生成。
- 图片插入。
- 用户上传图片。
- 任意 shape。
- shape fill color。
- 动画。
- 表格、图表、mask。
- Accessibility API。
- GUI 点击。

## 4. 为什么默认 Parchment

storybook deck 需要温暖、纸张感、儿童友好的默认视觉氛围。

Keynote 内置 `Parchment` 主题比较适合这个方向，而且不需要项目自己打包外部素材。

主题选择顺序：

1. `deck.theme`，如果 DeckSpec 里指定了。
2. `Parchment`。
3. `Basic White`。
4. Keynote 返回的第一个主题。

## 5. 新模块

新增：

```text
src/open_keynote_agent/renderers/
  __init__.py
  storybook.py
  templates.py
```

职责：

- `templates.py`：定义童话绘本 layout templates、坐标、object_id 规则。
- `storybook.py`：执行渲染流程，调用 Keynote 工具。

renderer 可以 import DeckSpec、ToolRegistry、execute_plan、Keynote tool registration。

renderer 不能 import LLM provider。

## 6. render_storybook_deck

核心函数：

```python
def render_storybook_deck(
    deck: DeckSpec,
    registry: ToolRegistry,
    state: SessionState,
    *,
    output_dir: Path,
    export_pdf: bool = True,
) -> RenderResult:
    ...
```

流程：

1. 调 `keynote.list_themes`。
2. 选择主题。
3. 调 `keynote.create_document`。
4. 调 `keynote.list_layouts`。
5. 复用 Keynote 新文档自带的默认第一页来渲染 `DeckSpec.slides[0]`。
6. 对 `DeckSpec.slides[1:]`：
   - add slide
   - set title
   - 根据模板添加 text box / emoji / rectangle
7. 如果 `export_pdf=True`，导出 PDF。
8. 返回 `RenderResult`。

如果任意工具调用失败，渲染要停止，并返回清晰错误。

## 7. 默认第一页约束

Keynote 的 `create_document` 会自动创建一个默认 slide。

如果 renderer 对 DeckSpec 的每一页都调用 `keynote.add_slide`，就会得到 `N+1` 页，其中第一页是孤立空白页。

所以 009 必须明确：

- `DeckSpec.slides[0]` 使用 Keynote 文档自带的默认第一页。
- 从 `DeckSpec.slides[1]` 开始才调用 `keynote.add_slide`。
- 本 MVP 要求第一页必须是 `cover`，因为默认第一页 layout 通常适合封面。
- 如果第一页不是 `cover`，renderer 应在创建/修改 Keynote 前失败。

## 8. RenderResult 和 tool_results

`RenderResult` 至少包含：

- `deck_title`
- `theme`
- `slide_count`
- `pdf_path`
- `output_dir`
- `tool_results`

`tool_results` 是 renderer 每次调用 `execute_plan` 后收集到的工具结果序列化记录。

CLI 写 `tool_results.jsonl` 时，数据来源就是：

```text
RenderResult.tool_results
```

如果没有这个字段，CLI 就没有可靠数据可以写 `tool_results.jsonl`。

## 9. Layout 映射

每种 slide kind 映射到语义 layout：

| Slide kind | Layout |
|---|---|
| `cover` | `title` |
| `characters` | `title_body` |
| `chapter` | `title_body` |
| `climax` | `title_body` |
| `lesson` | `title_body` |
| `ending` | `title` |
| `content` | `title_body` |

真实 Keynote layout 名称由 006 的 resolver 负责解析。

## 10. 童话绘本模板

MVP 使用 16:9 宽屏坐标假设。

模板应该是确定性的：

- 同一个 DeckSpec 每次生成相同工具调用。
- 坐标不是 LLM 生成的。
- object_id 是固定规则生成的。

示例 object_id：

```text
slide_01_title
slide_01_subtitle
slide_01_emoji_1
slide_01_panel
slide_08_the_end
```

## 11. 每种模板的大致行为

Cover：

- title layout。
- 设置标题。
- 有 subtitle 就加 subtitle text box。
- 添加大 emoji cluster。
- 可添加一个 rectangle 装饰 panel。

Characters：

- title_body layout。
- 标题 + body bullets。
- 最多 3 个 emoji 横向排列。

Chapter：

- title_body layout。
- 标题 + body。
- 1-3 个 emoji。
- 根据 slide index 左右交替摆放视觉区域，避免每页都一样。

Climax：

- title_body layout。
- 更强调标题和视觉 emoji。
- 适合狼、风、房子这类 emoji cluster。

Lesson：

- title_body layout。
- 强调故事启示。
- 添加温暖 emoji 或装饰。

Ending：

- title layout。
- 标题通常是 `The End`。
- 可添加 final message 和装饰 emoji。

Content：

- 通用 fallback。

## 12. Emoji 视觉

每页最多渲染 4 个 emoji。

使用：

```text
keynote.add_emoji_text
```

如果 DeckSpec 某页没有 emoji，则按 kind 选择 fallback：

- cover: `📖`
- characters: `🐷`
- climax: `🐺`
- ending: `✨`
- default: `⭐`

这样每页都至少有视觉元素。

## 13. Shape 视觉

当前 007 真实支持的 shape MVP 只有：

```json
{"shape": "rectangle"}
```

因此 009 只能用 rectangle 做简单装饰 panel 或分隔元素。

不能传：

- `rounded_rectangle`
- `oval`
- `line`
- `fill_color`

`VisualSpec.decorations` 是概念说明，不能直接转成 Keynote shape enum。

## 14. Text 渲染

标题优先用：

```text
keynote.set_slide_title
```

正文、subtitle、辅助说明用：

```text
keynote.add_text_box
```

字体大小使用模板里的固定值。

本 change 不要求自定义字体。

## 15. CLI：oka render-storybook

新增命令：

```bash
oka render-storybook <deck_spec.json>
```

选项：

```text
--output PATH
--no-pdf
```

本 change 不提供 `--tools` 选项。CLI 单元测试应通过 monkeypatch `register_keynote_tools` 或 `OsascriptRunner` 注入 fake 行为。未来如果需要再增加 `--tools`。

示例：

```bash
uv run oka render-storybook /tmp/three-pigs-plan/deck_spec.json --output /tmp/three-pigs-rendered
```

输出：

```text
render_result.json
tool_results.jsonl
rendered PDF
```

这个命令会打开并控制 Keynote，所以必须提示用户 macOS 可能弹出 Automation 权限请求。

## 16. 安全要求

- 不允许 LLM 生成 raw AppleScript。
- 不覆盖已有 PDF 或 result 文件。
- 不在 `deck-plan` 阶段偷偷渲染。
- 只有用户显式调用 `render-storybook` 才会控制 Keynote。
- 非 integration 测试不能依赖 Keynote。

## 17. 测试要求

单元测试必须使用 fake runner / fake tools。

覆盖：

- theme fallback。
- layout mapping。
- 默认 Keynote slide 1 被复用来渲染 `DeckSpec.slides[0]`。
- 只对 slides 2..N 调用 `keynote.add_slide`。
- 第一页不是 `cover` 时，在 mutation 前失败。
- object_id deterministic。
- fallback emoji。
- 不生成 unsupported shape。
- 不传 `fill_color`。
- 工具失败时停止渲染。
- CLI 读取 DeckSpec。
- CLI 写 render metadata。
- CLI 从 `RenderResult.tool_results` 写 `tool_results.jsonl`。
- CLI 不调用 LLM。

真实 Keynote 测试 opt-in：

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration
```

smoke test 使用三只小猪 DeckSpec fixture，渲染后导出 PDF，并确认 PDF 存在且非空。
