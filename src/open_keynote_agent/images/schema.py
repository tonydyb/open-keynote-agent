from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator


class ImageSpec(BaseModel):
    model_config = {"extra": "forbid"}

    prompt: str
    negative_prompt: str | None = None
    style: str = "storybook watercolor, warm children's book illustration"
    aspect_ratio: str = "16:9"
    output_format: Literal["png"] = "png"
    seed: int | None = None

    @field_validator("prompt")
    @classmethod
    def prompt_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be blank")
        return v

    @field_validator("aspect_ratio")
    @classmethod
    def aspect_ratio_supported(cls, v: str) -> str:
        supported = {"16:9"}
        if v not in supported:
            raise ValueError(f"aspect_ratio must be one of {supported}, got {v!r}")
        return v


class SlideArtSpec(BaseModel):
    model_config = {"extra": "forbid"}

    slide_index: int = Field(ge=1)
    slide_title: str
    image: ImageSpec

    @computed_field  # type: ignore[prop-decorator]
    @property
    def asset_filename(self) -> str:
        return f"slide_{self.slide_index:02d}.png"


class ImageAsset(BaseModel):
    model_config = {"extra": "forbid"}

    slide_index: int
    prompt_hash: str
    provider: str
    path: str
    cached: bool


class ImageManifest(BaseModel):
    model_config = {"extra": "forbid"}

    deck_title: str
    provider: str
    assets_dir: str
    assets: list[ImageAsset] = Field(default_factory=list)


class ImageGenerationResult(BaseModel):
    model_config = {"extra": "forbid"}

    provider: str
    path: str
    bytes_written: int
