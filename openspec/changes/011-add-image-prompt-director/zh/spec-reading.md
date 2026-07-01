# 011-add-image-prompt-director 中文阅读稿

## 1. 这个 spec 解决什么

010 已经能生成图片，而且 Stability Image Core 生成的清晰度和画面质量已经不错。

现在的问题不是“画得不够漂亮”，而是：

```text
图片模型不够听话
```

例如《白雪公主》里，某一页明明要求“邪恶皇后站在魔镜前”，模型却容易生成白雪公主、苹果、王子、餐桌、宴会等通用联想。

011 的目标是增加一个 deterministic image prompt director，让每页 prompt 更像“导演分镜”，而不是普通描述句子。

## 2. 和 010 的区别

010 是图片生成基础设施：

```text
DeckSpec -> SlideArtSpec -> ImageProvider -> assets/slide_01.png
```

011 是 prompt 准确度层：

```text
DeckSpec + SlideSpec
  -> DirectedImagePrompt
  -> 更强的 ImageSpec.prompt / negative_prompt
```

011 不负责调用 Bedrock，不负责生成 PNG，不负责插入 Keynote。

## 3. 非目标

011 不做这些事：

- 不调用 LLM。
- 不翻译 DeckSpec。
- 不新增图片 provider。
- 不修改 Bedrock invoke_model 逻辑。
- 不插入图片到 Keynote/PPTX/PDF。
- 不做视觉 QA。
- 不做完整角色一致性。

## 4. 新模型：DirectedImagePrompt

新增模型：

```python
class DirectedImagePrompt(BaseModel):
    slide_index: int
    slide_title: str
    primary_scene: str
    required_subjects: list[str] = []
    forbidden_subjects: list[str] = []
    composition: str | None = None
    style_notes: list[str] = []
    story_context: str | None = None
    prompt: str
    negative_prompt: str | None = None
```

它是中间层，不直接替代 `ImageSpec`。

最终仍然是：

```text
DirectedImagePrompt.prompt -> ImageSpec.prompt
DirectedImagePrompt.negative_prompt -> ImageSpec.negative_prompt
```

## 5. Prompt 顺序必须改变

旧 prompt 容易长这样：

```text
Story: Snow White.
Style: ...
Slide 4: The Evil Queen.
Scene description: ...
```

这样模型容易先被 `Snow White` 这个故事名带跑。

新 prompt 必须保证当前页画面在故事背景之前。

固定 preset mode 会先加一个风格锚点，帮助图片模型更认真服从风格：

```text
Image style, follow strongly:
paper_cut_collage_storybook — paper-cut collage picture-book look, layered paper texture, simple shapes...

Primary scene, follow exactly:
An evil queen wearing black and purple robes stands before a glowing magic mirror.

Required subjects:
- one evil queen
- one glowing magic mirror
- dark royal chamber

Story context:
Snow White. Use the story only as background context; do not add unrelated story elements.
```

`deck_style` mode 不加固定 preset 风格锚点，仍然从 primary scene 开始：

```text
Primary scene, follow exactly:
An evil queen wearing black and purple robes stands before a glowing magic mirror.

Required subjects:
- one evil queen
- one glowing magic mirror
- dark royal chamber

Story context:
Snow White. Use the story only as background context; do not add unrelated story elements.
```

也就是说，固定 preset 时是“风格先定调，当前页画面随后，故事名靠后”；`deck_style` 时是“当前页画面优先，故事名靠后”。

## 6. Required Subjects

每页应该明确“必须出现什么”。

来源包括：

- `slide.visual.description`
- slide title
- slide subtitle
- body bullets
- emoji 转换后的英文物体词

例如：

```text
Required subjects:
- evil queen
- glowing magic mirror
- dark royal chamber
```

第一版可以用保守启发式，不需要复杂 NLP。

## 7. Forbidden Subjects

每页也应该明确“不要出现什么”。

通用禁止项包括：

```text
text, caption, letters, words, watermark, logo, signature,
document, poster, user interface
```

还要加 `DeckSpec.style.avoid`。

可以加保守的 drift exclusions，例如：

- 当前页是魔镜/王宫房间：禁止 picnic、dining table、food。
- 当前页说 alone：禁止 extra people、duplicate main character。
- 当前页是 exterior：禁止 indoor dining、banquet table。

但不能写死：

```python
if deck.title == "Snow White":
    ...
```

也就是说，不允许 Snow White-only、Three Little Pigs-only、Frozen-only 的硬编码规则。

## 8. 风格 Mode

011 现在允许加入受控的儿童绘本插画风格 mode。

这不是 LLM 设计步骤，而是 deterministic prompt director 的一部分，用来避免图片模型跑向写实照片、电影剧照、成人肖像或 3D 渲染。

第一版支持 4 个 style mode：

- `soft_storybook_watercolor`
  - 默认值。
  - 温柔水彩儿童绘本风。
  - 关键词方向：hand-painted children's picture-book look, watercolor texture, soft edges, warm colors, simple composition, non-photorealistic characters。

- `cute_hand_drawn_cartoon`
  - 可爱手绘卡通绘本风。
  - 关键词方向：cute hand-drawn cartoon picture-book look, rounded simplified characters, expressive faces, bright friendly colors, clear child-readable shapes。

- `paper_cut_collage_storybook`
  - 纸艺拼贴绘本风。
  - 关键词方向：paper-cut collage picture-book look, layered paper texture, simple shapes, tactile craft materials, playful depth, child-friendly composition。

- `deck_style`
  - 使用 DeckSpec / VisualSpec 中的风格字段。
  - 这是 preview 阶段给用户看的 “Use My Prompt Style / 使用我的描述风格” 选项。

Style section 必须由选中的 style mode 决定。

如果选择三个固定 preset：

- prompt 以该 preset 作为主要视觉风格。
- 不自动混入 `DeckSpec.style.mood`。
- 不自动混入 `DeckSpec.style.typography`。
- 不自动混入 `DeckSpec.style.palette`。
- 不自动混入 `SlideSpec.visual.decorations`。
- 可以保留 `DeckSpec.style.audience` 作为受众上下文。

如果选择 `deck_style`：

- 使用 `DeckSpec.style.mood`。
- 使用 `DeckSpec.style.typography`。
- 使用 `DeckSpec.style.palette`。
- 使用 `SlideSpec.visual.decorations`。
- 不加入任何固定 preset 描述。

生成的 `art_spec.json` 里，`image.style` 必须写入当前选中的 style mode，例如 `soft_storybook_watercolor` 或 `deck_style`，不能继续写旧的中性占位值 `deck-specified`。

这样 preview 阶段会是干净的四选一，而不是把“水彩 + 剪纸 + 用户描述”揉在一起。

director 不应该再额外塞入 selected style mode 之外的固定美术风格。

negative prompt 里要加入默认风格护栏：

- not photorealistic
- not cinematic
- not realistic portrait
- not movie still
- not 3D render
- not adult editorial illustration

除非用户明确要求对应模式。

## 9. Dry Run

新增 prompt-only 模式：

```bash
uv run oka generate-images /tmp/snow-white-plan/deck_spec_en.json \
  --slides 1,4,9 \
  --dry-run \
  --output /tmp/snow-white-prompts
```

dry-run 行为：

- 读取 DeckSpec。
- 生成 selected slides 的 `art_spec.json`。
- 不调用 provider。
- 不需要 Bedrock/OpenAI credentials。
- 不生成 PNG。
- 不打开 Keynote。
- 不调用 LLM。

推荐 dry-run 不写 `image_manifest.json`，因为没有实际 image assets。

## 10. 推荐工作流

先看 prompt：

```bash
uv run oka generate-images deck_spec_en.json \
  --slides 1,4,9 \
  --dry-run \
  --output /tmp/prompts
```

确认 prompt 看起来合理后，再生成图片：

```bash
uv run oka generate-images deck_spec_en.json \
  --provider bedrock \
  --slides 1,4,9 \
  --style soft_storybook_watercolor \
  --output /tmp/preview
```

确认几页效果 OK 后，再全量生成。

也可以在 preview 阶段试不同风格：

```bash
uv run oka generate-images deck_spec_en.json \
  --slides 1,4,9 \
  --style cute_hand_drawn_cartoon \
  --dry-run \
  --output /tmp/prompts-cartoon
```

使用用户 prompt / DeckSpec 风格：

```bash
uv run oka generate-images deck_spec_en.json \
  --slides 1,4,9 \
  --style deck_style \
  --dry-run \
  --output /tmp/prompts-deck-style
```

## 11. 测试重点

需要测试：

- `DirectedImagePrompt` 校验。
- fixed preset prompt 开头必须是 `Image style, follow strongly`。
- `deck_style` prompt 开头必须是 primary scene。
- story context 必须在 primary scene 后面。
- required subjects 出现在 prompt。
- forbidden subjects 出现在 negative prompt。
- 默认 style mode 是 `soft_storybook_watercolor`。
- 三个固定 style mode 都能进入 prompt。
- 固定 preset 不会自动混入 `DeckSpec.style.mood`。
- `deck_style` 会使用 DeckSpec / VisualSpec 风格字段。
- `deck_style` 不会加入固定 preset 描述。
- `art_spec.json` 的 `image.style` 写入 selected style mode。
- style guardrails 进入 negative prompt。
- 未知 style mode 会清晰报错。
- 不注入 selected style mode 之外的固定美术风格。
- `build_slide_art_specs` 使用 directed prompt。
- `--dry-run` 写 `art_spec.json`。
- `--dry-run` 不调用 provider。
- `--dry-run --slides` 只写选中的页。
