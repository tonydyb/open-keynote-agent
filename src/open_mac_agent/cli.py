import typer
from pathlib import Path

from rich.console import Console
from rich.table import Table

from open_mac_agent.organizer import build_organize_plan
from open_mac_agent.filesystem import move_files
from open_mac_agent.runtime.session import create_run_session

app = typer.Typer(help="Open Mac Agent CLI")
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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(app.get_help(ctx))


@app.command()
def version():
    """Show the open-mac-agent version."""
    console.print("open-mac-agent 0.1.0")


@app.command()
def hello():
    """Print a simple confirmation message."""
    console.print("open-mac-agent is installed. Use `oma --help` for available commands.")


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

    session = create_run_session(folder, "oma organize")
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
        "target_dir": str(folder.resolve()),
        "moved": len(result.moved),
        "skipped": len(result.skipped),
    })
    session.write_result({
        "status": "confirmed",
        "operations": len(plan.operations),
        "moved": [str(path.relative_to(folder.resolve())) for path in result.moved],
        "skipped": [{"source": str(item.source.relative_to(folder.resolve())), "reason": item.reason} for item in result.skipped],
    })
    console.print(f"[bold green]Apply confirmed.[/] Moved {len(result.moved)} files.")
