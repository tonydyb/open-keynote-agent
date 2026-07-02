from __future__ import annotations

import os
import struct
import zlib
from base64 import b64decode
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv

from open_keynote_agent.images.schema import ImageGenerationResult, ImageSpec


class ImageProvider(Protocol):
    name: str

    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        """Write a PNG to output_path and return a result. Raises on failure."""
        ...


# ---------------------------------------------------------------------------
# Minimal valid 1x1 white PNG written with stdlib only (struct + zlib)
# ---------------------------------------------------------------------------

def _write_minimal_png(path: Path) -> int:
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8-bit RGB
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_row = b"\x00\xff\xff\xff"  # filter byte + R G B = white
    idat = _chunk(b"IDAT", zlib.compress(raw_row))
    iend = _chunk(b"IEND", b"")
    data = signature + ihdr + idat + iend
    path.write_bytes(data)
    return len(data)


class FakeImageProvider:
    name = "fake"

    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        n = _write_minimal_png(output_path)
        return ImageGenerationResult(provider=self.name, path=str(output_path), bytes_written=n)


# ---------------------------------------------------------------------------
# Bedrock image provider (Stability AI / Nova Canvas / Titan Image)
# ---------------------------------------------------------------------------

class BedrockImageProvider:
    name = "bedrock"

    def __init__(
        self,
        model_id: str,
        region: str | None = None,
        profile: str | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("OKA_IMAGE_MODEL is required for BedrockImageProvider")
        self.model_id = model_id
        self.region = region
        self.profile = profile

    def _build_request_body(self, spec: ImageSpec) -> dict:
        if self.model_id.startswith("stability."):
            body: dict = {
                "prompt": spec.prompt,
                "mode": "text-to-image",
                "aspect_ratio": spec.aspect_ratio,
                "output_format": spec.output_format,
            }
            if spec.negative_prompt:
                body["negative_prompt"] = spec.negative_prompt
            if spec.seed is not None:
                body["seed"] = spec.seed
            return body

        return self._build_amazon_request_body(spec)

    def _build_amazon_request_body(self, spec: ImageSpec) -> dict:
        body: dict = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": spec.prompt},
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "quality": "standard",
                "width": 1280,
                "height": 720,
                "cfgScale": 8.0,
            },
        }
        if spec.negative_prompt:
            body["textToImageParams"]["negativeText"] = spec.negative_prompt
        if spec.seed is not None:
            body["imageGenerationConfig"]["seed"] = spec.seed
        return body

    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError("boto3 is required for BedrockImageProvider") from exc

        import base64
        import json

        session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
        client = session.client("bedrock-runtime", region_name=self.region)

        body = self._build_request_body(spec)

        response = client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        response_body = json.loads(response["body"].read())
        images = response_body.get("images", [])
        if not images:
            raise RuntimeError("Bedrock returned no images")
        png_bytes = base64.b64decode(images[0])
        output_path.write_bytes(png_bytes)
        return ImageGenerationResult(
            provider=self.name,
            path=str(output_path),
            bytes_written=len(png_bytes),
        )


# ---------------------------------------------------------------------------
# OpenAI image provider
# ---------------------------------------------------------------------------

class OpenAIImageProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        size: str = "1536x1024",
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIImageProvider")
        if not model:
            raise ValueError("OKA_IMAGE_MODEL or OPENAI_IMAGE_MODEL is required for OpenAIImageProvider")
        self.api_key = api_key
        self.model = model
        self.size = size

    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai is required for OpenAIImageProvider") from exc

        client = OpenAI(api_key=self.api_key)
        response = client.images.generate(
            model=self.model,
            prompt=spec.prompt,
            n=1,
            size=self.size,
        )
        if not response.data:
            raise RuntimeError("OpenAI returned no images")
        b64_json = getattr(response.data[0], "b64_json", None)
        if not b64_json:
            raise RuntimeError("OpenAI image response did not include b64_json")
        png_bytes = b64decode(b64_json)
        output_path.write_bytes(png_bytes)
        return ImageGenerationResult(
            provider=self.name,
            path=str(output_path),
            bytes_written=len(png_bytes),
        )


# ---------------------------------------------------------------------------
# Gemini image provider
# ---------------------------------------------------------------------------

class GeminiImageProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiImageProvider")
        if not model:
            raise ValueError("OKA_IMAGE_MODEL or GEMINI_IMAGE_MODEL is required for GeminiImageProvider")
        self.api_key = api_key
        self.model = model

    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError("google-genai is required for GeminiImageProvider") from exc

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=spec.prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        image_bytes = _extract_gemini_image_bytes(response)
        if image_bytes is None:
            raise RuntimeError("Gemini returned no image data")
        output_path.write_bytes(image_bytes)
        return ImageGenerationResult(
            provider=self.name,
            path=str(output_path),
            bytes_written=len(image_bytes),
        )


def _extract_gemini_image_bytes(response: object) -> bytes | None:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return None
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None)
        if not parts:
            continue
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None:
                inline_data = getattr(part, "inlineData", None)
            if inline_data is None:
                continue
            data = getattr(inline_data, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return b64decode(data)
    return None


# ---------------------------------------------------------------------------
# Provider loader
# ---------------------------------------------------------------------------

class UnsupportedImageProviderError(ValueError):
    pass


def load_image_provider_from_env(provider_name: str | None = None) -> ImageProvider:
    if os.environ.get("OMA_SKIP_DOTENV") != "1":
        load_dotenv(dotenv_path=Path.cwd() / ".env")

    if provider_name is None:
        provider_name = os.environ.get("OKA_IMAGE_PROVIDER", "fake").lower()

    if provider_name == "fake":
        return FakeImageProvider()

    if provider_name == "bedrock":
        model_id = os.environ.get("OKA_IMAGE_MODEL", "")
        if not model_id:
            raise ValueError(
                "OKA_IMAGE_MODEL is required when OKA_IMAGE_PROVIDER=bedrock. "
                "Set it to a Bedrock image model ID, e.g. "
                "stability.stable-image-core-v1:1"
            )
        return BedrockImageProvider(
            model_id=model_id,
            region=os.environ.get("OKA_IMAGE_AWS_REGION") or os.environ.get("AWS_REGION"),
            profile=os.environ.get("AWS_PROFILE"),
        )

    if provider_name == "openai":
        return OpenAIImageProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OKA_IMAGE_MODEL")
            or os.environ.get("OPENAI_IMAGE_MODEL")
            or "gpt-image-2",
            size=os.environ.get("OKA_IMAGE_SIZE", "1536x1024"),
        )

    if provider_name == "gemini":
        return GeminiImageProvider(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            model=os.environ.get("OKA_IMAGE_MODEL")
            or os.environ.get("GEMINI_IMAGE_MODEL")
            or "gemini-3.1-flash-image",
        )

    raise UnsupportedImageProviderError(
        f"Unsupported image provider: {provider_name!r}. "
        "Valid providers are: fake, bedrock, openai, gemini."
    )
