import typer
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
from open_keynote_agent.tools.demo import register_demo_tools

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
) -> None:
    """Start an interactive agent session."""
    registry = ToolRegistry()
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
            results = execute_plan(plan, registry, state)

            observations: list[str] = []
            for step_index, result in enumerate(results):
                event_log.append(
                    "tool_called",
                    {"turn_index": turn_index, "step_index": step_index, "tool": result.tool, "args": result.args},
                )
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


if __name__ == "__main__":
    app()
