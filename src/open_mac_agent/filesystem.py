from pathlib import Path

from pydantic import BaseModel, Field

from open_mac_agent.organizer import OrganizePlan, SkippedFile


class MoveResult(BaseModel):
    moved: list[Path] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)


def move_files(plan: OrganizePlan) -> MoveResult:
    """Execute file moves from an OrganizePlan without overwriting existing files."""
    result = MoveResult()
    target_dir = plan.target_dir.resolve()

    for operation in plan.operations:
        source = operation.source
        destination = operation.destination

        try:
            destination.resolve().relative_to(target_dir)
        except ValueError:
            result.skipped.append(SkippedFile(source=source, reason="Unsafe destination path"))
            continue

        if not source.exists():
            result.skipped.append(SkippedFile(source=source, reason="Source file missing"))
            continue

        if destination.exists():
            result.skipped.append(SkippedFile(source=source, reason="Destination already exists"))
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        result.moved.append(destination)

    return result
