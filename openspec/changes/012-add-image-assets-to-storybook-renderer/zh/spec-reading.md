# 012-add-image-assets-to-storybook-renderer 中文阅读稿

## 1. 这个 spec 要解决什么

现在已经有两条流水线：

```text
DeckSpec -> Keynote emoji/shape storybook
DeckSpec -> image_manifest.json + assets/slide_XX.png
```

但图片还没有进入 Keynote。

012 的目标是把这两条线接起来：

```text
DeckSpec + image_manifest.json/assets
  -> Keynote storybook with images
  -> optional PDF
```

也就是说，用户可以先生成图片，再把这些图片插入 Keynote，每页一张主插画。

## 2. 012 不做什么

012 不做：

- 不生成图片。
- 不调用 LLM。
- 不优化 image prompt。
- 不新增 OpenAI image provider。
- 不做印刷级 PDF。
- 不做 CMYK / bleed / trim。
- 不替换成 PPTX 或 ReportLab。
- 不做视觉 QA。

012 只消费 010/011 生成好的图片。

## 3. 新增 Keynote 工具

新增：

```text
keynote.add_image
```

参数：

```json
{
  "slide": 1,
  "path": "/absolute/path/to/assets/slide_01.png",
  "x": 0,
  "y": 0,
  "width": 1280,
  "height": 720,
  "object_id": "slide_01_art"
}
```

要求：

- `path` 必须存在。
- `path` 必须是文件。
- 传给 AppleScript 前转成 absolute path。
- geometry 用 007 的 validator。
- object_id 用 007 的 object helper。
- context 里记录 `type = "image"`。
- context 里记录 `path/x/y/width/height/apple_class/apple_index`。

## 4. AppleScript Builder

新增：

```python
scripts.add_image(slide, path, x, y, width, height)
```

AppleScript 方向：

```applescript
tell application "Keynote"
  tell front document
    tell slide 1
      set imageItem to make new image with properties {file:POSIX file "/tmp/slide_01.png"}
      set position of imageItem to {0, 0}
      set width of imageItem to 1280
      set height of imageItem to 720
      return count of images
    end tell
  end tell
end tell
```

如果 Keynote 不接受 `make new image with properties {file:...}` 的某些属性，就采用 007 text item 的经验：先创建，再逐项 `set position/width/height`。

不要设置 Keynote object name。`object_id` 只保存在本地 context 中，和 text_box / shape 的策略一致。

## 5. Manifest 读取规则

输入是：

```text
/tmp/cinderella-art/image_manifest.json
```

manifest 里路径是相对路径：

```json
{
  "assets_dir": "assets",
  "assets": [
    {
      "slide_index": 1,
      "path": "assets/slide_01.png"
    }
  ]
}
```

解析规则：

```python
manifest_dir = image_manifest_path.parent
absolute_image_path = manifest_dir / asset.path
```

必须校验：

- manifest 文件存在。
- manifest 符合 `ImageManifest` schema。
- asset path 是 relative path。
- resolved image file 存在。
- duplicate slide_index 要报错。

## 6. 缺图时怎么处理

这里有两个不同情况：

### 情况 A：manifest 没有某一页

例如只生成了：

```text
slide_01.png
slide_04.png
slide_09.png
```

但 DeckSpec 有 12 页。

这种情况不应该失败。

没有图片的页继续使用 009 的 emoji/shape fallback。

### 情况 B：manifest 声明了某张图片，但文件不存在

例如 manifest 写了：

```json
{"slide_index": 4, "path": "assets/slide_04.png"}
```

但文件不存在。

这种情况必须失败，而且要在创建 Keynote 前失败。

## 7. Renderer 行为

`render_storybook_deck(...)` 增加可选图片输入。

有图片时：

- 调 `keynote.add_image`。
- 图片作为主视觉。
- 图片先插入，文字后插入，保证文字在图片上层。
- slides 2..N 使用 `blank` layout。
- slides 2..N 不再设置 Keynote 默认 title。
- 不再渲染原来的大 emoji 主视觉。
- 可以保留小装饰，但 MVP 可以先不保留。

没图片时：

- 保持 009 行为。
- 用 emoji + rectangle fallback。

额外图片：

- 如果 manifest 里有 DeckSpec 不存在的 slide index，不创建额外 slide。
- 可以忽略或 warning。

## 8. MVP 排版

先不要过度设计。

使用简单的 full-bleed 规则：

```text
image:
  x = 0
  y = 0
  width = 1280
  height = 720

text:
  overlay near bottom
```

有图片时：

- 第一页可以保留封面 title。
- 第二页以后不要使用大标题。
- 正文通过 `keynote.add_text_box` 作为图片上的 overlay。
- 自动文字颜色、半透明底板、避开人物主体等高级排版放到后续 spec。

重点是：

- 图片进 Keynote。
- 文字还能读。
- 一页 DeckSpec 对应一页 Keynote。

## 9. CLI

新增：

```bash
uv run oka render-storybook /tmp/cinderella-plan/deck_spec.json \
  --images /tmp/cinderella-art/image_manifest.json \
  --output /tmp/cinderella-rendered
```

保留：

```text
--output
--no-pdf
```

CLI 要求：

- 先校验 DeckSpec。
- 再校验 image manifest。
- manifest 无效或声明文件缺失时，不能创建/修改 Keynote。
- 输出 `render_result.json`。
- 输出 `tool_results.jsonl`。

## 10. 测试重点

需要测试：

- manifest relative path resolution。
- duplicate slide index 报错。
- manifest 声明的文件不存在时提前失败。
- manifest 缺某些 slide 时 fallback emoji。
- manifest 多余 slide 不创建 extra slides。
- `scripts.add_image` 生成正确 AppleScript。
- `keynote.add_image` 更新 object registry。
- renderer 对有图 slide 调 `keynote.add_image`。
- `tool_results.jsonl` 包含 image tool result。
- 没有 `--images` 时保持 009 行为。
- CLI `--images` 能把 manifest 传给 renderer。

真实 Keynote 测试继续 opt-in：

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration -s
```
