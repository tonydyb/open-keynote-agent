# 007-add-keynote-object-tools 中文阅读版

这份文档是 `007-add-keynote-object-tools` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 要在已有 Keynote AppleScript adapter 上增加“对象级编辑工具”。

006 已经解决了主题和 layout discovery：

- 列出 Keynote 内置主题。
- 用指定主题创建文档。
- 列出当前文档 layout。
- 把语义 layout，比如 `title_body`，解析成真实 Keynote layout 名称。

007 在这个基础上继续往前走：不只是创建 slide、设置默认标题和正文，而是能在某一页上添加和调整具体视觉对象。

目标工具包括：

- `keynote.add_text_box`：添加文本框。
- `keynote.add_emoji_text`：添加大号 emoji 文本。
- `keynote.add_shape`：添加基础装饰图形。
- `keynote.move_object`：移动之前创建的对象。
- `keynote.resize_object`：调整之前创建的对象尺寸。

这些工具是后续 storybook renderer、DeckSpec renderer、用户微调编辑能力的基础。

## 2. 为什么需要对象工具

只靠 `set_slide_title` 和 `set_slide_body` 做不出精美 Keynote。

比如“三只小猪”故事型 deck 需要：

- 大标题。
- 独立的文字块。
- 小猪、大灰狼等 emoji 视觉元素。
- 装饰色块或背景框。
- 每页不一样的位置和尺寸。
- 后续用户可以说“把 The End 放大一点”“把小猪 emoji 往右移”。

所以系统必须能创建可追踪对象，并在后续 turn 中继续引用这些对象。

## 3. 重要现实限制：Keynote 对象不能可靠命名

最初设计里曾经希望把本地 `object_id` 写进 Keynote 对象的 `object name` 属性，然后后续通过 `object name` 查找。

真实测试后发现：当前 Keynote AppleScript adapter 里，`text item` 和 `shape` 对象并没有可用的可写 `object name` / `name` 属性。

因此 007 的真实设计改成：

- `object_id` 只作为本地 session/context ID。
- 不尝试把 `object_id` 写入 Keynote 对象。
- 创建对象后，让 AppleScript 返回对象在当前 slide 集合里的索引。
- 本地 context 保存 `apple_class` 和 `apple_index`。
- 后续 move/resize 用 `slide + apple_class + apple_index` 定位对象。

也就是说：

```text
用户/agent 侧引用：object_id
Keynote 侧引用：apple_class + apple_index
```

示例：

```json
{
  "object_id": "slide_08_the_end",
  "slide": 8,
  "type": "text_box",
  "apple_class": "text item",
  "apple_index": 3,
  "x": 360,
  "y": 260,
  "width": 560,
  "height": 110,
  "text": "The End"
}
```

这个设计更接近真实 Keynote 能力，不假装 AppleScript 支持没有验证过的对象命名能力。

## 4. 本地 object_id 规则

每个被对象工具创建的对象都必须有稳定的 `object_id`。

用户或 planner 可以显式传入：

```text
slide_08_the_end
```

如果没有传入，系统自动生成：

```text
slide_{slide:02d}_{kind}_{n}
```

其中 `kind` 是：

- `text_box`
- `emoji`
- `shape`

示例：

```text
slide_01_text_box_1
slide_03_emoji_1
slide_08_shape_2
```

`object_id` 必须符合：

```text
^[a-z][a-z0-9_]{0,63}$
```

重复 `object_id` 必须在调用 AppleScript 前拒绝。

## 5. Context 对象注册表

007 会扩展 `context["keynote"]`，保存对象注册表：

```json
{
  "keynote": {
    "objects": {
      "slide_08_the_end": {
        "object_id": "slide_08_the_end",
        "slide": 8,
        "type": "text_box",
        "apple_class": "text item",
        "apple_index": 3,
        "x": 360,
        "y": 260,
        "width": 560,
        "height": 110,
        "text": "The End"
      }
    },
    "slides": {
      "8": {
        "objects": ["slide_08_the_end"]
      }
    }
  }
}
```

每个对象至少要记录：

- `object_id`
- `slide`
- `type`
- `apple_class`
- `apple_index`
- `x`
- `y`
- `width`
- `height`

文本和 emoji 对象还要记录 `text`。

shape 对象还要记录语义 `shape`。

`slides` 子索引用字符串页码，例如 `"8"`，不要用整数 `8`。这是因为 context 最终会被序列化成 JSON，字符串 key 更稳定。

## 6. 成功后才更新 context

所有对象工具都必须遵守 success-only update：

1. 先校验本地参数。
2. 生成 AppleScript。
3. 调用 runner。
4. 如果 runner 失败，不修改 context。
5. 如果 runner 成功，才注册对象或更新对象坐标/尺寸。

这样可以避免出现“Keynote 没创建成功，但 context 以为创建成功了”的状态错乱。

自动生成 `object_id` 的 counter 也只能在 runner 成功后提交。失败时不能污染 counter。

## 7. 坐标和尺寸校验

对象坐标使用 Keynote points：

```text
x: 左上角横坐标
y: 左上角纵坐标
width: 宽度
height: 高度
```

必须在调用 AppleScript 前校验：

- `slide >= 1`
- `x >= 0`
- `y >= 0`
- `width > 0`
- `height > 0`

如果 `context["keynote"]["slide_count"]` 已知，还要拒绝：

```text
slide > slide_count
```

## 8. keynote.add_text_box

用途：在指定 slide 上添加文本框。

示例参数：

```json
{
  "slide": 8,
  "text": "The End",
  "x": 360,
  "y": 260,
  "width": 560,
  "height": 110,
  "object_id": "slide_08_the_end",
  "font_size": 64,
  "font_color": "#6B3F1D"
}
```

真实 AppleScript 约束：

- 不要在 `make new text item` 的 properties record 里设置一堆属性。
- 先 bare create，再逐个设置属性。
- 不设置 `object name`。
- 最后返回 `count of text items`。

形态类似：

```applescript
set textItem to make new text item
set object text of textItem to "The End"
set position of textItem to {360, 260}
set width of textItem to 560
set height of textItem to 110
return count of text items
```

如果设置字体颜色，应该设置 rich text 的 object text color：

```applescript
set color of object text of textItem to {R, G, B}
```

不要直接在 text item 对象或 paragraph range 上设置 `text color`。

## 9. keynote.add_emoji_text

用途：把 emoji 当作大号文本对象添加到 slide 上。

示例参数：

```json
{
  "slide": 3,
  "emoji": "🐷",
  "x": 760,
  "y": 180,
  "size": 96,
  "object_id": "slide_03_pig_emoji"
}
```

实现上不需要单独的 `scripts.add_emoji_text()` builder。

handler 直接复用：

```text
scripts.add_text_box(text=emoji, ...)
```

size 映射规则固定为：

```text
width = size * 1.5
height = size * 1.5
font_size = size
```

`size <= 0` 必须在调用 runner 前拒绝。

## 10. keynote.add_shape

用途：添加基础装饰图形。

当前 MVP 只支持：

```text
rectangle
```

暂不支持：

- `rounded_rectangle`
- `oval`
- `line`
- `fill_color`

原因是当前真实 Keynote AppleScript 测试中，`shape type` 没有稳定可写路径，`background fill type` 也表现为只读。因此这版不假装支持。

示例参数：

```json
{
  "slide": 1,
  "shape": "rectangle",
  "x": 120,
  "y": 120,
  "width": 1000,
  "height": 420,
  "object_id": "slide_01_title_panel"
}
```

AppleScript 形态：

```applescript
set shapeItem to make new shape
set position of shapeItem to {120, 120}
set width of shapeItem to 1000
set height of shapeItem to 420
return count of shapes
```

如果用户传入 `fill_color`，必须在调用 runner 前失败，而不是静默忽略。

未知 shape 也必须在调用 runner 前失败。

## 11. keynote.move_object

用途：移动之前创建过的对象。

示例参数：

```json
{
  "object_id": "slide_08_the_end",
  "x": 320,
  "y": 240
}
```

执行流程：

1. 从 `context["keynote"]["objects"]` 查找 `object_id`。
2. 读取对象保存的 `slide`、`apple_class`、`apple_index`。
3. 生成 AppleScript，在对应 slide 上定位对象。
4. 设置新 position。
5. runner 成功后才更新 context 里的 `x`、`y`。

AppleScript 形态：

```applescript
tell slide 8
  set targetItem to text item 3
  set position of targetItem to {320, 240}
end tell
```

如果 `object_id` 不存在，必须在调用 runner 前失败。

## 12. keynote.resize_object

用途：调整之前创建过的对象尺寸。

示例参数：

```json
{
  "object_id": "slide_08_the_end",
  "width": 660,
  "height": 140
}
```

执行流程和 `move_object` 类似：

1. 从 context 查找对象。
2. 用 `apple_class` + `apple_index` 定位。
3. 设置新的 `width` 和 `height`。
4. runner 成功后才更新 context。

如果 `width <= 0` 或 `height <= 0`，必须在调用 runner 前失败。

## 13. 颜色处理

工具参数中颜色使用 hex：

```text
#F6A04D
#6B3F1D
```

转换成 Keynote 颜色值：

```text
#RRGGBB -> {round(R * 65535 / 255), round(G * 65535 / 255), round(B * 65535 / 255)}
```

当前：

- `font_color` 可以用于文本。
- `fill_color` 对 shape 暂不支持，必须拒绝。

原则是：如果用户提供了颜色参数，系统要么真的应用，要么提前失败，不能假装接受但实际忽略。

## 14. 测试要求

单元测试必须使用 `FakeScriptRunner`。

单元测试不需要：

- Keynote。
- `osascript`。
- macOS GUI。
- Automation 权限。

需要覆盖：

- object ID 校验和生成。
- 自动生成 ID 的 counter 只在成功后提交。
- duplicate object ID 拒绝。
- geometry 校验。
- invalid color 校验。
- `add_text_box` 生成正确 AppleScript 并更新 context。
- `add_emoji_text` 复用 text box builder。
- `add_shape` 只支持 rectangle。
- `rounded_rectangle`、`oval`、`line` 被拒绝。
- `fill_color` 被拒绝。
- `move_object` / `resize_object` 使用 `apple_class` + `apple_index`。
- runner 失败时 context 不变。

## 15. Integration smoke test

真实 Keynote 测试仍然必须 opt-in：

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration -s tests/test_keynote_tools.py
```

smoke test 应复用 006 的 discovery 流程：

1. list themes。
2. 优先选择 `Parchment`，否则 `Basic White`，否则第一个主题。
3. create document。
4. list layouts。
5. add `title_body` slide。
6. add text box。
7. add emoji text。
8. add rectangle shape。
9. move 或 resize 一个对象。
10. export PDF 并确认文件存在。

不要在 007 的 integration smoke 里测试 `rounded_rectangle`、`oval` 或 `fill_color`，因为这些不是当前真实支持的能力。

## 16. 本 change 不做什么

007 不做：

- 图片插入。
- 完整 deck renderer。
- advanced typography。
- animations。
- tables / charts。
- image masks。
- Accessibility API。
- GUI 点击。
- 任意 AppleScript 执行。

LLM 只能选择已注册工具和参数，本地代码负责校验和生成确定性 AppleScript。

## 17. 和后续 008/009 的关系

007 提供对象级工具能力。

008 会把用户长 prompt 转成 `DeckSpec JSON` 和 slide outline，但不会渲染 Keynote。

未来 renderer 可以消费 DeckSpec，然后调用 007 的对象工具：

```text
DeckSpec
  -> deterministic layout templates
  -> keynote.add_text_box
  -> keynote.add_emoji_text
  -> keynote.add_shape
  -> keynote.move_object / resize_object
```

但 renderer 必须尊重 007 当前真实能力边界：shape MVP 只有 `rectangle`，shape fill 暂不支持。
