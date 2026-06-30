from __future__ import annotations

import os
import struct
import zlib
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

    raise UnsupportedImageProviderError(
        f"Unsupported image provider: {provider_name!r}. "
        "Valid providers are: fake, bedrock."
    )
