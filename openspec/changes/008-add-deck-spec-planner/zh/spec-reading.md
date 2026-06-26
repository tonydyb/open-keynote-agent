# 008-add-deck-spec-planner 中文阅读版

这份文档是 `008-add-deck-spec-planner` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 要增加一个 DeckSpec planning 层：

```text
用户长 prompt -> DeckSpec JSON -> 结构校验 -> slide outline
```

它不负责真正生成 Keynote 文件，也不调用 `keynote.*` 工具。

008 的重点是把用户的大段自然语言需求，先变成一个稳定、可校验、可审阅的中间结构。后续 renderer 才会读取这个结构，并调用 006/007 已经实现的 Keynote 工具去真正画 slide。

可以把它理解成：

```text
用户说想要什么
  -> 008 变成结构化设计稿
  -> 用户/agent 可以检查设计稿
  -> 后续 change 再根据设计稿渲染 Keynote
```

## 2. 为什么需要 DeckSpec

当前 `oka session` 已经可以把一句话规划成几个工具调用。

但像下面这种请求太大：

```text
请为我制作一个关于《三只小猪》故事的精美 Keynote 演示文稿。
故事结构 8 张幻灯片：封面、角色介绍、稻草屋、木头屋、砖头屋、高潮、结局与主题、结束页。
风格童话绘本风，暖色调，每张都有 emoji 或装饰视觉元素，不要蓝色商务风。
```

如果直接让 LLM 生成一长串 `keynote.add_text_box` / `keynote.add_shape` 调用，会很难检查，也容易出错。

更稳的方式是先生成 DeckSpec：

- deck 标题是什么。
- 主题风格是什么。
- 一共有几页。
- 每页是什么类型。
- 每页标题、正文、视觉元素是什么。
- 每页有什么 emoji / 装饰建议。

这个 DeckSpec 是后续 renderer 的输入。

## 3. 本 change 做什么

008 要做：

- 新增 `src/open_keynote_agent/deck/` 包。
- 定义 Pydantic v2 数据模型：
  - `DeckSpec`
  - `SlideSpec`
  - `StyleSpec`
  - `VisualSpec`
- 实现 `plan_deck_spec(...)`。
- 实现 `render_deck_outline(...)`。
- 增加 CLI 命令：

```bash
oka deck-plan "<brief>"
```

- 把结果写到：

```text
request.json
deck_spec.json
outline.md
```

- 用 `FakeLLMClient` 做测试。

## 4. 本 change 不做什么

008 不做：

- 不打开 Keynote。
- 不调用 `keynote.*` tools。
- 不调用 AppleScript。
- 不生成真正的 `.key` 文件。
- 不导出 PDF。
- 不生成图片。
- 不支持用户上传图片 prompt。
- 不做 frontend GUI。
- 不设计每个对象的精确坐标。

它只是规划层，不是渲染层。

## 5. deck 包结构

新增：

```text
src/open_keynote_agent/deck/
  __init__.py
  schema.py
  planner.py
  outline.py
```

职责：

- `schema.py`：定义 DeckSpec 相关 Pydantic 模型。
- `planner.py`：调用 LLM，把用户 brief 转成 DeckSpec。
- `outline.py`：把 DeckSpec 渲染成人类可读 markdown outline。

这个包必须保持纯规划层，不能 import：

- `open_keynote_agent.tools.keynote`
- `open_keynote_agent.applescript`
- `OsascriptRunner`

## 6. Pydantic v2 模型规则

所有 DeckSpec 相关模型都要使用 Pydantic v2。

每个模型都要：

```python
model_config = {"extra": "forbid"}
```

这样 LLM 如果返回 schema 之外的字段，本地会拒绝，而不是静默接受。

所有 list 默认值必须用：

```python
Field(default_factory=list)
```

不要写：

```python
palette: list[str] = []
```

避免可变默认值问题。

## 7. DeckSpec

`DeckSpec` 表示整个 deck：

```python
class DeckSpec(BaseModel):
    title: str
    subtitle: str | None = None
    language: str | None = None
    theme: str | None = "Parchment"
    style: StyleSpec
    slides: list[SlideSpec]
```

校验要求：

- `title` 必须非空。
- `language` 默认是 `None`，不要默认写死成 `zh`。
- `slides` 至少 1 页，最多 20 页。
- slide index 必须从 1 开始连续递增。

比如 8 页 deck 的 index 必须是：

```text
1, 2, 3, 4, 5, 6, 7, 8
```

不能从 0 开始：

```text
0, 1, 2, ...
```

你之前实际测试遇到的报错：

```text
slides.0.index
Value error, index must be >= 1
```

就是这个校验在工作。LLM 返回了 `index = 0`，本地 DeckSpec 拒绝了它。

实现上应让 `model_json_schema()` 也把这些限制暴露给 LLM，例如：

- `SlideSpec.index` 用 `Field(ge=1)`。
- `DeckSpec.slides` 用 `Field(min_length=1, max_length=20)`。

## 8. StyleSpec

`StyleSpec` 描述整体风格：

```python
class StyleSpec(BaseModel):
    mood: str
    audience: str | None = None
    palette: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    typography: str | None = None
```

示例：

```json
{
  "mood": "童话绘本风，温暖可爱",
  "audience": "儿童",
  "palette": ["orange", "yellow", "brown", "green"],
  "avoid": ["blue business style"],
  "typography": "large playful titles, readable body text"
}
```

`mood` 必须非空。

`avoid` 用来记录用户明确不要的方向，比如“不想要蓝色商务风”。

## 9. SlideSpec

`SlideSpec` 表示一页 slide：

```python
class SlideSpec(BaseModel):
    index: int
    kind: Literal[
        "cover",
        "characters",
        "chapter",
        "climax",
        "lesson",
        "ending",
        "content",
    ]
    title: str
    subtitle: str | None = None
    body: list[str] = Field(default_factory=list)
    visual: VisualSpec
    layout_hint: str | None = None
    speaker_notes: str | None = None
```

支持的 `kind`：

- `cover`
- `characters`
- `chapter`
- `climax`
- `lesson`
- `ending`
- `content`

校验要求：

- `index >= 1`
- `title` 非空
- 每页都必须有 `visual`

这样后续 renderer 不会收到纯文字页。

## 10. VisualSpec

`VisualSpec` 描述每页的视觉元素计划：

```python
class VisualSpec(BaseModel):
    description: str
    emoji: list[str] = Field(default_factory=list)
    decorations: list[str] = Field(default_factory=list)
    placement_hint: str | None = None
```

校验要求：

- `description` 非空。
- `emoji` 必须是 list。
- `decorations` 必须是 list。
- `emoji` 中每个 item 都必须是非空字符串。
- `decorations` 中每个 item 都必须是非空字符串。

示例：

```json
{
  "description": "Three cute pigs and a wolf in a warm storybook style",
  "emoji": ["🐷", "🐷", "🐷", "🐺"],
  "decorations": ["warm parchment frame", "small straw/wood/brick motifs"],
  "placement_hint": "large visual cluster on the right"
}
```

注意：`decorations` 是概念性视觉说明，不是直接传给 `keynote.add_shape` 的枚举。

这是因为 007 当前真实支持的 shape MVP 只有 `rectangle`，不支持 `rounded_rectangle`、`oval`、`fill_color`。DeckSpec 不应该过早绑定到具体渲染工具能力。

## 11. plan_deck_spec

planner 函数：

```python
def plan_deck_spec(
    brief: str,
    llm_client: LLMClient,
    *,
    slide_count_hint: int | None = None,
    theme_hint: str | None = "Parchment",
) -> DeckSpec:
    ...
```

执行流程：

1. 校验 `brief.strip()` 非空。
2. 如果提供 `slide_count_hint`，校验范围是 `1..20`。
3. 构造 system/user messages。
4. 调用：

```python
llm_client.complete_json(messages, DeckSpec.model_json_schema())
```

5. 用：

```python
DeckSpec.model_validate(raw)
```

校验 LLM 返回。

6. 返回 validated `DeckSpec`。

planner prompt 必须告诉 LLM：

- 只返回 JSON。
- 按 schema 返回。
- 每页都要有 visual description。
- 如果用户要求 emoji / 装饰元素，要写进 `visual`。
- 如果用户要求不要蓝色商务风，要写进 style/avoid。
- 童话绘本类 deck 优先用 `Parchment` theme。
- `language` 根据用户 brief 主语言推断，不要硬编码。
- slide index 必须从 1 开始，不是从 0 开始。

planner 不能写文件，也不能调用 Keynote。

## 12. render_deck_outline

outline renderer：

```python
def render_deck_outline(deck: DeckSpec) -> str:
    ...
```

它把 DeckSpec 转成人类可读 markdown。

应该包含：

- deck title
- subtitle
- theme
- style summary
- slide index
- slide kind
- slide title
- body bullets
- visual description
- emoji
- decorations

示例：

```markdown
# 三只小猪与大灰狼

Theme: Parchment
Style: 童话绘本风，温暖可爱

## Slides

1. Cover — 三只小猪与大灰狼
   Visual: 🐷 🐷 🐷 🐺 — Three cute pigs and a wolf

2. Characters — 认识三只小猪
   Body:
   - 大毛：贪玩，喜欢稻草屋
   - 二毛：聪明一点，但还不够努力
   - 小毛：勤劳、有耐心
   Visual: 🐷 🐷 🐷 — character lineup
```

outline 主要给用户/开发者审阅，也方便后续调试。

## 13. CLI：oka deck-plan

新增命令：

```bash
oka deck-plan "<brief>"
```

支持选项：

```text
--slides INTEGER
--theme TEXT
--output PATH
```

示例：

```bash
uv run oka deck-plan "请为我制作一个关于《三只小猪》的 8 页童话绘本风 Keynote" --slides 8 --theme Parchment
```

指定输出目录：

```bash
uv run oka deck-plan "请为我制作一个关于《三只小猪》的 8 页童话绘本风 Keynote" --slides 8 --theme Parchment --output /tmp/three-pigs-deck-plan
```

命令会写：

```text
request.json
deck_spec.json
outline.md
```

`deck_spec.json` 必须使用：

```python
ensure_ascii=False
```

这样中文不会被转义成 `\u4e09\u53ea...`。

## 14. 默认输出目录

如果用户没有传 `--output`，输出目录应在：

```text
.runs/<YYYYMMDDTHHMMSSZ>/
```

这个格式要和 `runtime/session.py` 保持一致。

如果同一秒内已有同名目录，就加 suffix：

```text
.runs/20260626T120000Z-1/
.runs/20260626T120000Z-2/
```

不能覆盖已有目录。

## 15. CLI 失败行为

如果以下任一阶段失败：

- LLM provider 加载失败。
- LLM completion 失败。
- DeckSpec validation 失败。

CLI 必须：

- 非 0 退出。
- 打印简洁的用户错误。
- 不写 `request.json`。
- 不写 `deck_spec.json`。
- 不写 `outline.md`。
- 如果是默认 `.runs` 输出目录，不能留下半成品目录。

如果用户显式传了 `--output`，命令可以留下空目录，但不能写半成品文件。

## 16. Three Little Pigs 示例要求

对于“三只小猪” prompt，planner 应该输出：

- 7-8 页。
- 标题类似 `三只小猪与大灰狼`。
- 风格是童话绘本、温暖、儿童友好。
- 每页都有 visual spec。
- 每页有 emoji 或 decorations。
- 明确避免蓝色商务风。
- theme 优先 `Parchment`。

这不是 renderer 的最终画面，只是结构化设计稿。

## 17. 测试要求

测试必须使用 `FakeLLMClient`。

测试不能依赖：

- 真实 LLM credentials。
- Keynote。
- `osascript`。
- macOS Automation 权限。

需要覆盖：

- schema valid / invalid。
- blank brief 在调用 LLM 前失败。
- invalid slide_count_hint 在调用 LLM 前失败。
- `DeckSpec.model_json_schema()` 被传给 LLM。
- LLM 返回 malformed JSON-like dict 时被拒绝。
- slide index 从 1 开始。
- outline 内容稳定。
- CLI 写三个文件。
- CLI 拒绝覆盖已有输出文件。
- CLI 失败时不写 partial files。
- 默认 `.runs` 目录 timestamp collision 会加 suffix。

## 18. 和 007/009 的关系

007 提供对象级 Keynote 工具：

- add text box
- add emoji text
- add rectangle shape
- move object
- resize object

008 不使用这些工具，只生成 DeckSpec。

未来 009 或 renderer change 可以读取 DeckSpec：

```text
DeckSpec
  -> deterministic layout templates
  -> keynote.add_text_box
  -> keynote.add_emoji_text
  -> keynote.add_shape
  -> export_pdf
```

但 renderer 必须尊重 007 的真实能力边界：当前 shape MVP 只有 `rectangle`，shape fill 暂不支持。
