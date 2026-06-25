from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from open_keynote_agent.organizer import CATEGORY_EXTENSIONS, DEFAULT_CATEGORY


SUPPORTED_CATEGORIES = set(CATEGORY_EXTENSIONS) | {DEFAULT_CATEGORY}


class OrganizeRequest(BaseModel):
    target_dir: Path
    categories: Optional[list[str]] = None
    dry_run: bool = True

    model_config = {
        "extra": "forbid",
    }

    @field_validator("target_dir", mode="before")
    def validate_target_dir(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Target directory does not exist: {path}")
        return path.resolve()

    @field_validator("categories")
    def validate_categories(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None

        invalid = [category for category in value if category not in SUPPORTED_CATEGORIES]
        if invalid:
            raise ValueError(
                f"Unsupported categories: {invalid}. Supported categories are {sorted(SUPPORTED_CATEGORIES)}"
            )
        return value


class LLMPlanResponse(BaseModel):
    organize_request: OrganizeRequest

    model_config = {
        "extra": "forbid",
    }


def validate_llm_plan(payload: dict[str, Any]) -> LLMPlanResponse:
    return LLMPlanResponse.model_validate(payload)
