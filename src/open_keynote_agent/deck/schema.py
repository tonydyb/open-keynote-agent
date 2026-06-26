from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StyleSpec(BaseModel):
    model_config = {"extra": "forbid"}

    mood: str
    audience: str | None = None
    palette: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    typography: str | None = None

    @field_validator("mood")
    @classmethod
    def mood_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("mood must not be blank")
        return v


class VisualSpec(BaseModel):
    model_config = {"extra": "forbid"}

    description: str
    emoji: list[str] = Field(default_factory=list)
    decorations: list[str] = Field(default_factory=list)
    placement_hint: str | None = None

    @field_validator("description")
    @classmethod
    def description_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description must not be blank")
        return v

    @field_validator("emoji", "decorations", mode="before")
    @classmethod
    def items_nonempty(cls, v: object) -> object:
        if not isinstance(v, list):
            raise ValueError("emoji and decorations must be lists")
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("list items must be non-empty strings")
        return v


class SlideSpec(BaseModel):
    model_config = {"extra": "forbid"}

    index: int = Field(ge=1)
    kind: Literal["cover", "characters", "chapter", "climax", "lesson", "ending", "content"]
    title: str
    subtitle: str | None = None
    body: list[str] = Field(default_factory=list)
    visual: VisualSpec
    layout_hint: str | None = None
    speaker_notes: str | None = None

    @field_validator("index")
    @classmethod
    def index_ge_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("index must be >= 1")
        return v

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v


class DeckSpec(BaseModel):
    model_config = {"extra": "forbid"}

    title: str
    subtitle: str | None = None
    language: str | None = None
    theme: str | None = "Parchment"
    style: StyleSpec
    slides: list[SlideSpec] = Field(min_length=1, max_length=20)

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v

    @field_validator("slides")
    @classmethod
    def slides_count_range(cls, v: list[SlideSpec]) -> list[SlideSpec]:
        if len(v) < 1 or len(v) > 20:
            raise ValueError(f"slides must have 1..20 items, got {len(v)}")
        return v

    @model_validator(mode="after")
    def slides_sequential(self) -> "DeckSpec":
        for expected, slide in enumerate(self.slides, start=1):
            if slide.index != expected:
                raise ValueError(
                    f"slide indexes must be sequential starting at 1; "
                    f"expected {expected}, got {slide.index}"
                )
        return self
