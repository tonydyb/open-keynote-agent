# Open Keynote Agent

1つのプロンプトから、macOS 上で子ども向け絵本風の Keynote デッキと PDF を生成します。

このプロジェクトは、AI による Keynote 制作支援を試すためのオープンソース・プロトタイプです。できること：

- 物語プロンプトからバイリンガルな `DeckSpec` を作成
- 各スライド用の挿絵画像を生成
- 挿絵と本文を Keynote に配置
- PDF として書き出し

実装詳細、アーキテクチャ、過去のマイルストーンは [doc/TECHNICAL.md](doc/TECHNICAL.md) を参照してください。

## 必要なもの

- Apple Keynote がインストールされた macOS
- `uv`
- 物語設計用の LLM provider
- 挿絵生成用の image provider

依存関係をインストール：

```bash
uv sync --all-extras
```

環境変数ファイルをコピー：

```bash
cp .env.example .env
```

## 推奨 `.env`

OpenAI が最も簡単なエンドツーエンド設定です：

```bash
OMA_LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o

OKA_IMAGE_PROVIDER=openai
OPENAI_IMAGE_MODEL=gpt-image-2
OKA_IMAGE_SIZE=1024x768
```

`1024x768` は、多くの Mac で Keynote の組み込み Parchment テーマから書き出される 4:3 ページに合います。

Gemini と Bedrock も利用できます：

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

## ワンコマンドで絵本を生成

`.env` を設定したあと、リポジトリのルートで実行します：

```bash
STORY="『嫦娥奔月』を題材にした、4〜8歳向けの子ども用絵本 Keynote を作成してください。" \
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

出力フォルダには次のファイルが含まれます：

- `render_result.json`
- `tool_results.jsonl`
- 書き出された PDF
- Keynote で開かれた絵本ファイル
