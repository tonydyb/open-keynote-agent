# 010-add-image-asset-generation 中文阅读版

这份文档是 `010-add-image-asset-generation` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

010 要做图片资产生成：

```text
DeckSpec
  -> 每页插画 prompt
  -> ImageProvider
  -> PNG 文件
  -> image_manifest.json
```

它不打开 Keynote，不调用 `keynote.*`，也不把图片插入 slide。

010 的输出是后续 011/012 使用的图片资产：

```text
.runs/.../assets/slide_01.png
.runs/.../assets/slide_02.png
...
```

## 2. 为什么需要这一层

009 已经证明：

```text
DeckSpec -> Keynote -> PDF
```

这条链路能跑通。

但 009 只有文字、emoji、rectangle，视觉效果比较粗糙。

如果想做接近儿童绘本/动画截图那种精美效果，核心缺口是插画图片。因此 010 先生成每页插画 PNG，再由后续 change 插入 Keynote。

## 3. 本 change 做什么

010 要做：

- 定义 `ImageSpec`。
- 定义 `SlideArtSpec`。
- 从 `DeckSpec` 生成每页 image prompt。
- 定义 `ImageProvider` 协议。
- 实现 `FakeImageProvider`。
- 实现 `BedrockImageProvider` 作为默认真实图片 provider。
- 可选实现 `OpenAIImageProvider` 作为第二真实 provider。
- 保存 PNG 到 `assets/slide_01.png`。
- 写 `art_spec.json`。
- 写 `image_manifest.json`。
- 做缓存，避免 prompt 没变时重复生成。
- 增加 CLI：

```bash
oka generate-images <deck_spec.json>
```

## 4. 本 change 不做什么

010 不做：

- 不插入 Keynote。
- 不调用 AppleScript。
- 不调用 `keynote.*`。
- 不渲染 slide。
- 不导出 PDF。
- 不做图片编辑、局部重绘、upscale。
- 不解决跨页角色一致性。
- 不做 GUI。

## 5. 模块结构

新增：

```text
src/open_keynote_agent/images/
  __init__.py
  schema.py
  planner.py
  provider.py
  generator.py
```

职责：

- `schema.py`：图片相关 Pydantic 模型。
- `planner.py`：从 DeckSpec 生成 SlideArtSpec。
- `provider.py`：ImageProvider 协议和 fake/真实 provider。
- `generator.py`：生成图片、缓存、写 manifest。

这个 package 不能 import Keynote tools 或 AppleScript。

## 6. ImageSpec

`ImageSpec` 描述一张图片怎么生成：

```python
class ImageSpec(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    style: str = "storybook watercolor, warm children's book illustration"
    aspect_ratio: str = "16:9"
    output_format: Literal["png"] = "png"
    seed: int | None = None
```

校验：

- `prompt` 非空。
- `aspect_ratio` 当前只支持 `16:9`。
- `output_format` 当前只支持 `png`。

## 7. SlideArtSpec

`SlideArtSpec` 表示某一页对应的插画计划：

```python
class SlideArtSpec(BaseModel):
    slide_index: int
    slide_title: str
    image: ImageSpec
    asset_filename: str
```

校验：

- `slide_index >= 1`
- `asset_filename == slide_{index:02d}.png`

注意：`asset_filename` 应该用 Pydantic `@computed_field` 从 `slide_index` 推导出来，不应该让调用方自己传。这样可以避免 `slide_index=1` 但 `asset_filename="slide_02.png"` 这种不一致。

例如：

```text
slide_01.png
slide_02.png
```

## 8. Prompt 生成

函数：

```python
build_slide_art_specs(deck: DeckSpec) -> list[SlideArtSpec]
```

它不调用 LLM。

它从已有 DeckSpec 字段拼出每页 image prompt：

- deck title
- style mood
- audience
- slide title
- subtitle
- body bullets
- visual description
- emoji
- decorations

prompt 必须包含：

```text
no text, no captions, no letters, no watermark
```

因为图片模型很容易在图里乱生成文字，而我们希望文字由 Keynote 排版层负责。

示例：

```text
Children's storybook watercolor illustration for "三只小猪与大灰狼".
Slide 3: 第一章 — 大毛的稻草屋.
Scene: A straw house in a sunny meadow. Include: 🐷 🌾 🏠.
Warm orange, yellow, brown, green palette. Cute, friendly, hand-painted.
No text, no captions, no letters, no watermark.
```

## 9. ImageProvider

定义协议：

```python
class ImageProvider(Protocol):
    name: str
    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        ...
```

provider 负责把 PNG 写到指定路径。

`name` 是 provider 的稳定名字，代码里要能通过 `provider.name` 读到。实现时可以用 class-level constant：

```python
class FakeImageProvider:
    name = "fake"
```

provider loader 不应该依赖 Python class name 来判断 provider 类型。

`ImageGenerationResult` 是一个明确模型，不是可选的临时返回值：

```python
class ImageGenerationResult(BaseModel):
    provider: str
    path: str
    bytes_written: int
```

provider 失败时应该抛出清晰异常，不要返回半成功状态。

## 10. FakeImageProvider

`FakeImageProvider` 是必做的。

它必须：

- 不访问网络。
- 不需要 API key。
- 写出合法 PNG 文件。
- 输出稳定，适合测试。

可以使用内置 base64 tiny PNG，或者用本地库生成简单 PNG。测试只需要确认：

- 文件存在。
- PNG signature 正确。
- 没有调用真实 API。

## 11. Provider：默认 Fake，显式 Bedrock，可选 OpenAI

010 支持的 provider：

```text
OKA_IMAGE_PROVIDER=fake|bedrock
```

这里使用 `OKA_` 前缀是有意的，因为现在 CLI 已经是 `oka`。已有的 `OMA_LLM_PROVIDER` 暂时作为历史 LLM 配置保留，不在 010 里机械重命名。

provider 策略：

- `fake`：`OKA_IMAGE_PROVIDER` 未设置时的默认 provider，适合测试和无网络本地开发。
- `bedrock`：主要真实 provider，需要通过 `OKA_IMAGE_PROVIDER=bedrock` 或 `--provider bedrock` 显式选择。
- `openai`：预留给后续可选 provider；010 当前不要求实现。

默认行为：

```text
OKA_IMAGE_PROVIDER 未设置 -> fake
真实生成 -> OKA_IMAGE_PROVIDER=bedrock
```

Bedrock provider 必须隔离在 adapter 里。

要求：

- 实现 `BedrockImageProvider`。
- 从 `OKA_IMAGE_MODEL` 读取 Bedrock image model id。
- 尽量复用现有 AWS/Bedrock credentials 和 region 约定。
- 不要把唯一支持模型 hardcode 成某一个 Bedrock model。
- AWS credentials、region、model access 或配置缺失时，要给清晰错误。
- 测试不能调用 Bedrock。
- 输出必须写成 PNG。

OpenAI provider 是可选的。如果实现：

- 实现 `OpenAIImageProvider`。
- 从 `OKA_IMAGE_MODEL` 读取 OpenAI image model id。
- `OPENAI_API_KEY` 或 model 配置缺失时，要给清晰错误。

如果真实 provider 需要第三方包，必须在 `pyproject.toml` 里新增专门的 optional dependency group：

```toml
[project.optional-dependencies]
images = [...]
```

如果不加 `images` extra，那么真实 provider 只能使用 stdlib HTTP 或项目已经有的依赖。

这层不要和 Keynote 绑定。

## 12. 缓存机制

为了避免重复花钱/等待，010 必须做缓存。

hash 规则：

```text
prompt_hash = sha256(canonical ImageSpec JSON + provider name)[:16]
```

其中 canonical JSON 必须固定为：

```python
canonical = json.dumps(
    spec.model_dump(mode="json"),
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)
prompt_hash = sha256(f"{provider.name}\n{canonical}".encode("utf-8")).hexdigest()[:16]
```

010 只有在调用方传入 `cache_dir` 时才使用共享缓存：

```text
<cache_dir>/<prompt_hash>.png
```

如果 `cache_dir is None`，库函数不会使用共享缓存，避免测试或不同调用之间互相污染。同一个 `output_dir` 内的 manifest 复用仍然有效。

如果已有 manifest 中某页满足：

- slide index 一样。
- provider 一样。
- prompt hash 一样。
- asset path 存在。

或者在传入 `cache_dir` 时，共享缓存里已经有对应 provider/hash 的 PNG，就直接复用，不再调用 provider。复用时要把共享缓存中的 PNG 拷贝到本次 run 的：

```text
assets/slide_XX.png
```

manifest 中记录：

```json
{
  "slide_index": 1,
  "prompt_hash": "...",
  "provider": "fake",
  "path": "assets/slide_01.png",
  "cached": true
}
```

新生成则：

```json
"cached": false
```

`--force` 可以强制重新生成。

`--force` 会绕过共享缓存和当前 output manifest，重新调用 provider，并替换当前 run 的 asset 文件；如果传入了 `cache_dir`，也刷新共享缓存文件。

## 13. generate_image_assets

核心函数：

```python
def generate_image_assets(
    deck: DeckSpec,
    provider: ImageProvider,
    *,
    output_dir: Path,
    force: bool = False,
    cache_dir: Path | None = None,
) -> ImageManifest:
    ...
```

如果 `cache_dir is None`，共享缓存关闭。

流程：

1. 生成 SlideArtSpec。
2. 创建 `<output_dir>/assets/`。
3. 读取已有 `image_manifest.json`。
4. 对每页检查缓存。
5. 没缓存则调用 provider。
6. 写 `art_spec.json`。
7. 写 `image_manifest.json`。
8. 返回 manifest。

文件路径：

```text
<output_dir>/assets/slide_01.png
<output_dir>/assets/slide_02.png
```

不能写到 `output_dir` 外面。

唯一例外是调用方显式传入的 `cache_dir`。run artifact，包括 `art_spec.json`、`image_manifest.json`、`assets/slide_XX.png`，都必须在 `output_dir` 内。

`art_spec.json` 内容固定为：

```json
{
  "deck_title": "...",
  "slides": [
    {
      "slide_index": 1,
      "slide_title": "...",
      "image": {},
      "asset_filename": "slide_01.png"
    }
  ]
}
```

`image_manifest.json` 里的路径要可移植：

```json
{
  "assets_dir": "assets",
  "assets": [
    {
      "path": "assets/slide_01.png"
    }
  ]
}
```

也就是说，`assets_dir` 和 `path` 都是相对于 `image_manifest.json` 所在目录的相对路径，不存绝对路径。

写 manifest 时使用本地 CLI 足够安全的原子写：

```text
先写 image_manifest.json.tmp
再用 Path.replace() 替换 image_manifest.json
```

## 14. CLI：oka generate-images

新增命令：

```bash
oka generate-images <deck_spec.json>
```

选项：

```text
--output PATH
--provider TEXT
--force
```

示例：

```bash
uv run oka generate-images /tmp/three-pigs-plan/deck_spec.json --output /tmp/three-pigs-art
```

默认输出目录：

```text
.runs/<YYYYMMDDTHHMMSSZ>-images/
```

如果重名，加 suffix：

```text
.runs/20260626T120000Z-images-1/
```

## 15. 输出结构

输出目录应类似：

```text
three-pigs-art/
  art_spec.json
  image_manifest.json
  assets/
    slide_01.png
    slide_02.png
    slide_03.png
```

后续 012 可以读取 `image_manifest.json`，把 PNG 插入 Keynote。

如果调用方传入 `cache_dir`，它不是某一次 run 的正式输出，只用于避免重复生成。

## 16. 测试要求

测试必须不依赖：

- 真实图片 API。
- 网络。
- API key。
- Keynote。
- AppleScript。
- macOS Automation 权限。

覆盖：

- model validation。
- prompt construction。
- 每个 slide 生成一个 art spec。
- fake provider 写 PNG。
- manifest 输出。
- cache hit 不调用 provider。
- 默认新建 timestamp output 目录时，也能通过共享缓存命中。
- prompt 变化导致 cache miss。
- `--force` 重新生成。
- CLI 层 `--force` 也要有测试，证明它会绕过共享缓存并重新调用 provider。
- CLI 写 assets 和 manifest。
- CLI 不调用 Keynote。

## 17. 后续关系

011 可以增加：

```text
keynote.add_image
```

012 可以把：

```text
deck_spec.json + image_manifest.json
```

合并渲染成真正图文并茂的 Keynote。
