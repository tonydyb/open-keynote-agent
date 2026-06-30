import json
import typer
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from open_keynote_agent.filesystem import move_files
from open_keynote_agent.llm.parser import load_llm_client_from_env, parse_natural_language_request
from open_keynote_agent.organizer import build_organize_plan
from open_keynote_agent.organizer import OrganizePlan
from open_keynote_agent.runtime.session import create_run_session
from open_keynote_agent.agent.executor import execute_plan
from open_keynote_agent.agent.planner import PlanValidationError, plan_turn
from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import SessionState, Turn
from open_keynote_agent.runtime.events import EventLog
from open_keynote_agent.applescript.runner import OsascriptRunner
from open_keynote_agent.tools.demo import register_demo_tools
from open_keynote_agent.tools.keynote import register_keynote_tools
from open_keynote_agent.deck.planner import plan_deck_bundle
from open_keynote_agent.deck.outline import render_deck_outline
from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.renderers.storybook import render_storybook_deck
from open_keynote_agent.images.generator import generate_image_assets
from open_keynote_agent.images.provider import UnsupportedImageProviderError, load_image_provider_from_env

app = typer.Typer(help="Open Keynote Agent CLI")
console = Console()


def render_organize_plan(target_dir: Path, operations: list, skipped: list) -> None:
    if operations:
        table = Table(title="Organize plan")
        table.add_column("Source", style="cyan")
        table.add_column("Destination", style="magenta")
        table.add_column("Category", style="green")

        for op in operations:
            relative_destination = op.destination.relative_to(target_dir)
            table.add_row(str(op.source.name), str(relative_destination), op.category)

        console.print(table)
    else:
        console.print("[yellow]No files were selected for organization.[/]")

    if skipped:
        skipped_table = Table(title="Skipped files")
        skipped_table.add_column("Source", style="cyan")
        skipped_table.add_column("Reason", style="red")
        for skipped_file in skipped:
            skipped_table.add_row(str(skipped_file.source.name), skipped_file.reason)
        console.print(skipped_table)


def _relative_to_target(path: Path, target_dir: Path) -> str:
    try:
        return str(path.relative_to(target_dir))
    except ValueError:
        return str(path)


def handle_plan(
    *,
    session,
    plan: OrganizePlan,
    target_dir: Path,
    dry_run: bool,
) -> None:
    render_organize_plan(plan.target_dir, plan.operations, plan.skipped)

    if dry_run:
        session.write_result({
            "status": "dry_run",
            "operations": len(plan.operations),
            "skipped": len(plan.skipped),
        })
        console.print("[bold green]Dry-run mode: no files were moved.[/]")
        return

    if not plan.operations:
        session.write_result({
            "status": "no_operations",
            "operations": 0,
            "skipped": len(plan.skipped),
        })
        console.print("[yellow]No operations to apply.[/]")
        return

    confirmed = typer.confirm("Apply these moves?", default=False)
    if not confirmed:
        session.write_result({
            "status": "cancelled",
            "operations": len(plan.operations),
            "skipped": len(plan.skipped),
        })
        console.print("[yellow]Apply cancelled. No files were moved.[/]")
        return

    result = move_files(plan)
    session.append_tool_call({
        "tool": "move_files",
        "target_dir": str(target_dir),
        "moved": len(result.moved),
        "skipped": len(result.skipped),
    })
    session.write_result({
        "status": "confirmed",
        "operations": len(plan.operations),
        "moved": [_relative_to_target(path, target_dir) for path in result.moved],
        "skipped": [
            {"source": _relative_to_target(item.source, target_dir), "reason": item.reason}
            for item in result.skipped
        ],
    })
    console.print(f"[bold green]Apply confirmed.[/] Moved {len(result.moved)} files.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(app.get_help(ctx))


@app.command()
def version():
    """Show the open-keynote-agent version."""
    console.print("open-keynote-agent 0.1.0")


@app.command()
def hello():
    """Print a simple confirmation message."""
    console.print("open-keynote-agent is installed. Use `oka --help` for available commands.")


@app.command()
def organize(
    folder: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview file moves without applying them."),
    apply: bool = typer.Option(False, "--apply", help="Prompt to apply the file move plan."),
) -> None:
    """Plan folder organization by file category."""
    if dry_run and apply:
        raise typer.BadParameter("Cannot specify both --dry-run and --apply.")

    if not dry_run and not apply:
        dry_run = True

    session = create_run_session(folder, "oka organize")
    session.write_request({
        "command": "organize",
        "target_dir": str(folder.resolve()),
        "mode": "dry-run" if dry_run else "apply",
        "dry_run": dry_run,
        "apply": apply,
    })

    plan = build_organize_plan(folder)
    session.write_plan(plan.model_dump())
    session.append_tool_call({
        "tool": "build_organize_plan",
        "target_dir": str(folder.resolve()),
        "operations": len(plan.operations),
        "skipped": len(plan.skipped),
    })

    handle_plan(session=session, plan=plan, target_dir=folder.resolve(), dry_run=dry_run)


@app.command()
def ask(
    request: str = typer.Argument(..., help="Natural-language file organization request."),
    apply: bool = typer.Option(False, "--apply", help="Prompt to apply the generated file move plan."),
) -> None:
    """Convert a natural-language request into a validated organization plan."""
    client = load_llm_client_from_env()
    try:
        response = parse_natural_language_request(client, request)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc

    organize_request = response.organize_request
    target_dir = organize_request.target_dir.resolve()
    dry_run = not apply or organize_request.dry_run

    session = create_run_session(target_dir, "oka ask")
    session.write_request({
        "command": "ask",
        "request": request,
        "target_dir": str(target_dir),
        "categories": organize_request.categories,
        "mode": "dry-run" if dry_run else "apply",
        "dry_run": dry_run,
        "apply": apply,
    })
    session.append_tool_call({
        "tool": "parse_natural_language_request",
        "target_dir": str(target_dir),
        "categories": organize_request.categories,
        "dry_run": organize_request.dry_run,
    })

    plan = build_organize_plan(target_dir, categories=organize_request.categories)
    session.write_plan(plan.model_dump())
    session.append_tool_call({
        "tool": "build_organize_plan",
        "target_dir": str(target_dir),
        "operations": len(plan.operations),
        "skipped": len(plan.skipped),
    })

    handle_plan(session=session, plan=plan, target_dir=target_dir, dry_run=dry_run)


@app.command()
def session(
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation prompts (for scripting/tests)."),
    tools: str = typer.Option("demo", "--tools", help="Tool set to register: 'demo' (default) or 'keynote'."),
) -> None:
    """Start an interactive agent session."""
    if tools not in ("demo", "keynote"):
        raise typer.BadParameter(f"Invalid --tools value {tools!r}. Valid values: demo, keynote.")

    registry = ToolRegistry()
    if tools == "keynote":
        console.print("[yellow]Note: macOS may prompt for permission to control Keynote via Automation.[/]")
        register_keynote_tools(registry, OsascriptRunner())
    else:
        register_demo_tools(registry)

    llm_client = load_llm_client_from_env()
    state = SessionState()
    log_path = Path(".runs") / state.session_id / "events.jsonl"
    event_log = EventLog(log_path)

    event_log.append("session_start", {"session_id": state.session_id})
    console.print(f"[dim]Session {state.session_id}. Type 'done' to exit.[/]")

    turn_index = 0
    while True:
        try:
            instruction = typer.prompt("oka", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt):
            break

        if instruction.strip().lower() in ("done", "exit", "quit", ""):
            break

        event_log.append("turn_start", {"turn_index": turn_index, "instruction": instruction})

        try:
            plan = plan_turn(instruction, state, registry, llm_client)
        except PlanValidationError as exc:
            event_log.append("plan_error", {"turn_index": turn_index, "error": str(exc)})
            console.print(f"[red]Plan error:[/] {exc}")
            turn_index += 1
            continue

        event_log.append(
            "plan_proposed",
            {
                "turn_index": turn_index,
                "steps": [{"tool": s.tool, "args": s.args, "description": s.description} for s in plan.steps],
            },
        )

        console.print("[bold]Plan:[/]")
        for i, step in enumerate(plan.steps, 1):
            console.print(f"  {i}. {step.description}")

        if not plan.steps:
            console.print("[yellow]No steps proposed.[/]")
            turn_index += 1
            continue

        has_mutating = any(
            (registry.get(s.tool) and registry.get(s.tool).mutating)  # type: ignore[union-attr]
            for s in plan.steps
        )

        approved = True
        if has_mutating and not no_confirm:
            approved = typer.confirm("Apply?", default=False)

        if approved:
            event_log.append("plan_approved", {"turn_index": turn_index})

            def _on_step_start(step_index: int, step) -> None:
                event_log.append(
                    "tool_called",
                    {"turn_index": turn_index, "step_index": step_index, "tool": step.tool, "args": step.args},
                )

            results = execute_plan(plan, registry, state, on_step_start=_on_step_start)

            observations: list[str] = []
            for step_index, result in enumerate(results):
                event_log.append(
                    "tool_result",
                    {
                        "turn_index": turn_index,
                        "step_index": step_index,
                        "ok": result.ok,
                        "output": result.output,
                        "error": result.error,
                        "observation": result.observation,
                    },
                )
                if result.ok:
                    console.print(f"[green]>[/] {result.observation}")
                else:
                    console.print(f"[red]Error:[/] {result.observation}")
                observations.append(result.observation)

            state.turns.append(
                Turn(
                    instruction=instruction,
                    plan=plan,
                    approved=True,
                    results=results,
                    observations=observations,
                )
            )
        else:
            event_log.append("plan_rejected", {"turn_index": turn_index})
            console.print("[yellow]Skipped.[/]")
            state.turns.append(
                Turn(instruction=instruction, plan=plan, approved=False)
            )

        turn_index += 1

    event_log.append("session_end", {"session_id": state.session_id, "turn_count": turn_index})
    console.print("[dim]Session ended.[/]")


@app.command(name="deck-plan")
def deck_plan(
    brief: str = typer.Argument(..., help="Natural-language presentation brief."),
    slides: int | None = typer.Option(None, "--slides", help="Optional slide count hint (1..20)."),
    theme: str = typer.Option("Parchment", "--theme", help="Optional Keynote theme hint."),
    output: Path | None = typer.Option(None, "--output", help="Output directory (default: unique dir under .runs/)."),
) -> None:
    """Convert a presentation brief into a validated DeckSpec JSON and slide outline."""
    try:
        client = load_llm_client_from_env()
        bundle = plan_deck_bundle(brief, client, slide_count_hint=slides, theme_hint=theme)
    except Exception as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    default_dir_created: Path | None = None
    if output is None:
        base = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        candidate = Path(".runs") / base
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = Path(".runs") / f"{base}-{suffix}"
        candidate.mkdir(parents=True)
        out_dir = candidate
        default_dir_created = candidate
    else:
        out_dir = output
        out_dir.mkdir(parents=True, exist_ok=True)

    output_files = ("request.json", "deck_spec.json", "deck_spec_en.json", "outline.md", "outline_en.md")
    for name in output_files:
        if (out_dir / name).exists():
            console.print(f"[red]Error:[/] Output file already exists: {out_dir / name}")
            if default_dir_created is not None:
                default_dir_created.rmdir()
            raise typer.Exit(code=1)

    localized = bundle.localized
    english = bundle.english
    request_data = {
        "command": "deck-plan",
        "brief": brief,
        "slides": slides,
        "theme": theme,
        "source_language": localized.source_language or localized.language,
        "localized_language": localized.content_language or localized.language,
        "english_language": english.content_language or english.language,
        "generated_files": list(output_files),
    }
    (out_dir / "request.json").write_text(
        json.dumps(request_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "deck_spec.json").write_text(
        json.dumps(localized.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "deck_spec_en.json").write_text(
        json.dumps(english.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    outline_text = render_deck_outline(localized)
    (out_dir / "outline.md").write_text(outline_text, encoding="utf-8")
    outline_en_text = render_deck_outline(english)
    (out_dir / "outline_en.md").write_text(outline_en_text, encoding="utf-8")

    console.print(outline_text)
    console.print(f"[dim]Output written to {out_dir}[/]")


@app.command(name="render-storybook")
def render_storybook(
    deck_spec_path: Path = typer.Argument(..., help="Path to deck_spec.json produced by oka deck-plan."),
    output: Path | None = typer.Option(None, "--output", help="Output directory (default: unique dir under .runs/)."),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Skip PDF export."),
) -> None:
    """Render a validated DeckSpec into a Keynote storybook presentation."""
    if not deck_spec_path.exists() or not deck_spec_path.is_file():
        console.print(f"[red]Error:[/] File not found: {deck_spec_path}")
        raise typer.Exit(code=1)

    try:
        deck = DeckSpec.model_validate_json(deck_spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        console.print(f"[red]Error:[/] Invalid DeckSpec: {exc}")
        raise typer.Exit(code=1) from exc

    if output is None:
        base = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-storybook"
        candidate = Path(".runs") / base
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = Path(".runs") / f"{base}-{suffix}"
        candidate.mkdir(parents=True)
        out_dir = candidate
        default_dir_created: Path | None = candidate
    else:
        out_dir = output
        out_dir.mkdir(parents=True, exist_ok=True)
        default_dir_created = None

    for name in ("render_result.json", "tool_results.jsonl"):
        if (out_dir / name).exists():
            console.print(f"[red]Error:[/] Output file already exists: {out_dir / name}")
            if default_dir_created is not None:
                default_dir_created.rmdir()
            raise typer.Exit(code=1)

    pdf_file = out_dir / f"{deck.title}.pdf"
    if not no_pdf and pdf_file.exists():
        console.print(f"[red]Error:[/] PDF already exists: {pdf_file}")
        if default_dir_created is not None:
            default_dir_created.rmdir()
        raise typer.Exit(code=1)

    console.print("[yellow]Note: macOS may prompt for permission to control Keynote via Automation.[/]")

    from open_keynote_agent.agent.registry import ToolRegistry
    from open_keynote_agent.agent.session import SessionState

    registry = ToolRegistry()
    register_keynote_tools(registry, OsascriptRunner())
    state = SessionState()

    try:
        result = render_storybook_deck(
            deck, registry, state,
            output_dir=out_dir,
            export_pdf=not no_pdf,
        )
    except Exception as exc:
        console.print(f"[red]Render error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    (out_dir / "render_result.json").write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (out_dir / "tool_results.jsonl").open("w", encoding="utf-8") as fh:
        for record in result.tool_results:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    console.print(f"[bold green]Rendered:[/] {result.slide_count} slides")
    console.print(f"[dim]Output: {out_dir}[/]")
    if result.pdf_path:
        console.print(f"[dim]PDF: {result.pdf_path}[/]")


@app.command(name="generate-images")
def generate_images(
    deck_spec_path: Path = typer.Argument(..., help="Path to deck_spec_en.json or deck_spec.json produced by oka deck-plan."),
    output: Path | None = typer.Option(None, "--output", help="Output directory (default: unique dir under .runs/)."),
    provider: str | None = typer.Option(None, "--provider", help="Image provider: fake or bedrock (default from OKA_IMAGE_PROVIDER or fake)."),
    force: bool = typer.Option(False, "--force", help="Ignore cache and regenerate all images."),
) -> None:
    """Generate per-slide illustration PNG assets from a validated DeckSpec."""
    if not deck_spec_path.exists() or not deck_spec_path.is_file():
        console.print(f"[red]Error:[/] File not found: {deck_spec_path}")
        raise typer.Exit(code=1)

    try:
        deck = DeckSpec.model_validate_json(deck_spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        console.print(f"[red]Error:[/] Invalid DeckSpec: {exc}")
        raise typer.Exit(code=1) from exc

    try:
        image_provider = load_image_provider_from_env(provider)
    except (ValueError, UnsupportedImageProviderError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    default_dir_created: Path | None = None
    if output is None:
        base = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-images"
        candidate = Path(".runs") / base
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = Path(".runs") / f"{base}-{suffix}"
        candidate.mkdir(parents=True)
        out_dir = candidate
        default_dir_created = candidate
    else:
        out_dir = output
        out_dir.mkdir(parents=True, exist_ok=True)

    try:
        shared_cache = Path(".runs") / "image-cache" / image_provider.name
        manifest = generate_image_assets(
            deck, image_provider, output_dir=out_dir, force=force, cache_dir=shared_cache
        )
    except Exception as exc:
        console.print(f"[red]Error:[/] {exc}")
        if default_dir_created is not None and default_dir_created.exists():
            import shutil
            shutil.rmtree(default_dir_created, ignore_errors=True)
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Generated:[/] {len(manifest.assets)} images")
    console.print(f"[dim]Assets: {out_dir / 'assets'}[/]")
    console.print(f"[dim]Manifest: {out_dir / 'image_manifest.json'}[/]")


if __name__ == "__main__":
    app()
