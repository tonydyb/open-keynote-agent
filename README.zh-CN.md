# Open Keynote Agent

用一句提示词在 macOS 上生成儿童绘本风 Keynote 和 PDF。

这是一个开源原型项目，用来探索 AI 辅助 Keynote 创作。它可以：

- 根据故事提示生成双语 `DeckSpec`
- 为每页生成插画图片
- 把插画和文字排版到 Keynote 中
- 导出 PDF

技术架构、实现细节和历史里程碑见 [doc/TECHNICAL.md](doc/TECHNICAL.md)。

## 环境要求

- macOS，并安装 Apple Keynote
- `uv`
- 至少一个用于故事规划的 LLM provider
- 至少一个用于插画生成的 image provider

安装依赖：

```bash
uv sync --all-extras
```

复制环境变量模板：

```bash
cp .env.example .env
```

## 推荐 `.env`

OpenAI 是最简单的端到端配置：

```bash
OMA_LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o

OKA_IMAGE_PROVIDER=openai
OPENAI_IMAGE_MODEL=gpt-image-2
OKA_IMAGE_SIZE=1024x768
```

`1024x768` 适合很多 Mac 上 Keynote 内置 Parchment 主题导出的 4:3 页面。

也支持 Gemini 和 Bedrock：

```bash
# Gemini
OMA_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
OKA_IMAGE_PROVIDER=gemini
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image

# Bedrock
OMA_LLM_PROVIDER=bedrock
AWS_PROFILE=default
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=your-bedrock-llm-model
OKA_IMAGE_PROVIDER=bedrock
OKA_IMAGE_AWS_REGION=us-west-2
OKA_IMAGE_MODEL=stability.stable-image-core-v1:1
```

## 一条命令生成绘本

配置好 `.env` 后，在项目根目录运行：

```bash
STORY="请为我制作一本关于《嫦娥奔月》的儿童绘本 Keynote，适合 4-8 岁儿童。" \
SLIDES=20 \
OUT=~/Downloads/oka-change-flying-to-the-moon \
bash -lc '
set -euo pipefail
rm -rf "$OUT-plan" "$OUT-prompts" "$OUT-art" "$OUT-rendered"

uv run oka deck-plan "$STORY" \
  --slides "$SLIDES" \
  --theme Parchment \
  --output "$OUT-plan"

uv run oka generate-images "$OUT-plan/deck_spec_en.json" \
  --dry-run \
  --slides 1,4,8 \
  --style soft_storybook_watercolor \
  --output "$OUT-prompts"

uv run oka generate-images "$OUT-plan/deck_spec_en.json" \
  --style soft_storybook_watercolor \
  --output "$OUT-art"

uv run oka render-storybook "$OUT-plan/deck_spec.json" \
  --images "$OUT-art/image_manifest.json" \
  --output "$OUT-rendered"

open "$OUT-rendered"
'
```

输出目录包含：

- `render_result.json`
- `tool_results.jsonl`
- 导出的 PDF
- Keynote 打开的绘本文件
