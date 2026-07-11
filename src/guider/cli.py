from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from guider.config.loader import get_config, get_config_path, init_config
from guider.dashboard import run_dashboard
from guider.doctor import run_doctor
from guider.mcp.server import run_server
from guider.reporting import governance_report
from guider.service import GuiderService
from guider.storage.database import get_database
from guider.watch import watch_events

app = typer.Typer(
    name="ai-guider",
    help="AI Guider — local-first MCP server for AI agent governance",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run MCP server when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        run_server()


@app.command()
def init(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    cursor: bool = typer.Option(
        False, "--cursor", help="Configure Cursor MCP and governance rule"
    ),
    hooks: bool = typer.Option(
        False, "--hooks", help="Install Cursor session + pre-edit AI Guider hooks"
    ),
    claude: bool = typer.Option(
        False, "--claude", help="Configure Claude Code (~/.claude.json) + instructions"
    ),
    claude_desktop: bool = typer.Option(
        False, "--claude-desktop", help="Configure Claude Desktop app MCP"
    ),
    codex: bool = typer.Option(
        False, "--codex", help="Configure OpenAI Codex CLI (~/.codex/config.toml)"
    ),
    all_clients: bool = typer.Option(
        False, "--all-clients", help="Configure Cursor+hooks, Claude Code, Claude Desktop, Codex"
    ),
    project_mcp: Optional[Path] = typer.Option(
        None,
        "--project-mcp",
        help="Also write .mcp.json into this project directory (Claude Code project scope)",
    ),
) -> None:
    """Initialize AI Guider configuration and optionally wire MCP clients."""
    from guider.client_setup import setup_clients

    path = init_config(config_path)
    db = get_database()
    console.print(f"[green]✓[/green] Config created at {path}")
    console.print(f"[green]✓[/green] Database initialized at {db.db_path}")

    do_cursor = cursor or hooks or all_clients
    do_hooks = hooks or all_clients
    do_claude = claude or all_clients
    do_desktop = claude_desktop or all_clients
    do_codex = codex or all_clients

    if not any([do_cursor, do_claude, do_desktop, do_codex, project_mcp]):
        console.print("\nAdd to your MCP client config:")
        console.print(
            json.dumps(
                {"mcpServers": {"ai-guider": {"command": "ai-guider"}}},
                indent=2,
            )
        )
        console.print(
            "\nOr run: [cyan]ai-guider init --all-clients[/cyan]\n"
            "  Flags: [cyan]--cursor --hooks --claude --claude-desktop --codex[/cyan]"
        )
        return

    report = setup_clients(
        cursor=do_cursor,
        cursor_hooks=do_hooks,
        claude_code=do_claude,
        claude_desktop=do_desktop,
        codex=do_codex,
        project_path=project_mcp,
    )
    console.print(f"[green]✓[/green] MCP command: {report['command']}")

    for name, info in (report.get("clients") or {}).items():
        if name == "cursor":
            console.print(f"[green]✓[/green] Cursor MCP: {info.get('mcp_config')}")
            console.print(f"[green]✓[/green] Cursor rule: {info.get('cursor_rule')}")
            if info.get("hooks"):
                console.print(f"[green]✓[/green] Cursor hooks: {info['hooks']['hooks_json']}")
                console.print("  Reload Cursor window to activate hooks.")
        elif name == "claude_code":
            console.print(f"[green]✓[/green] Claude Code MCP: {info.get('config')}")
            if info.get("claude_md"):
                console.print(f"[green]✓[/green] Claude instructions: {info.get('claude_md')}")
            console.print("  Restart Claude Code / start a new session to load MCP.")
        elif name == "claude_desktop":
            console.print(f"[green]✓[/green] Claude Desktop MCP: {info.get('config')}")
            console.print("  Fully quit and reopen Claude Desktop to load MCP.")
        elif name == "codex":
            console.print(f"[green]✓[/green] Codex MCP: {info.get('config')}")
            if info.get("instructions"):
                console.print(f"[green]✓[/green] Codex guide: {info.get('instructions')}")
            console.print("  Restart Codex / run [cyan]codex mcp list[/cyan] to verify.")

    if report.get("project_mcp_json"):
        console.print(f"[green]✓[/green] Project .mcp.json: {report['project_mcp_json']}")


@app.command()
def status() -> None:
    """Show AI Guider runtime status."""
    config = get_config()
    db = get_database()
    stats = db.get_stats()

    table = Table(title="AI Guider Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Profile", config.profile)
    table.add_row("Config", str(get_config_path()))
    table.add_row("Database", stats["database_path"])
    table.add_row("Missions", str(stats["missions"]))
    table.add_row("Active Missions", str(stats["active_missions"]))
    table.add_row("Events", str(stats["events"]))
    table.add_row("Decisions", str(stats["decisions"]))
    table.add_row("Pending Questions", str(stats.get("pending_questions", 0)))

    console.print(table)


@app.command()
def resume(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace path"
    ),
) -> None:
    """Show active mission, pending questions, and recent events."""
    svc = GuiderService()
    data = svc.resume_mission(str(workspace) if workspace else None)
    if not data.get("mission_id"):
        console.print("[yellow]No active mission. Start with govern_request(phase='start').[/yellow]")
        return
    console.print(f"[cyan]Mission[/cyan] {data['mission_id']}  ({data.get('status')})")
    console.print(f"[cyan]Objective[/cyan] {data.get('objective')}")
    console.print(f"[cyan]Confidence[/cyan] {data.get('confidence_score', 0):.0%}")
    pending = data.get("pending_questions") or {}
    qs = pending.get("questions") or []
    if qs:
        console.print(f"\n[yellow]Pending questions ({len(qs)})[/yellow]")
        for q in qs:
            console.print(f"  • {q.get('unknown')}: {q.get('question')}")
            if q.get("suggested_answer"):
                console.print(f"    suggested: {q['suggested_answer']}")
    else:
        console.print("\n[green]No pending questions[/green]")
    events = data.get("recent_events") or []
    if events:
        console.print("\n[cyan]Recent events[/cyan]")
        for e in events[:5]:
            console.print(f"  • {e.get('event_type')}: {e.get('message')}")
    for step in data.get("next_steps") or []:
        console.print(f"[dim]→ {step}[/dim]")


@app.command()
def doctor() -> None:
    """Run health checks on AI Guider installation."""
    ok, results = run_doctor()
    table = Table(title="AI Guider Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for r in results:
        style = {"ok": "green", "warn": "yellow", "fail": "red"}.get(r["status"], "white")
        table.add_row(r["check"], f"[{style}]{r['status']}[/{style}]", r["detail"])
    console.print(table)
    if not ok:
        raise typer.Exit(1)


@app.command()
def report(
    mission_id: Optional[str] = typer.Option(None, "--mission", "-m"),
) -> None:
    """Show governance compliance report."""
    data = governance_report(get_database(), mission_id)
    console.print_json(data=data)


@app.command()
def export(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    project_path: Path = typer.Argument(..., help="Project directory"),
) -> None:
    """Export mission to .ai-guider/mission.yaml and AGENTS.md."""
    svc = GuiderService()
    result = svc.export_mission(mission_id, str(project_path))
    console.print(f"[green]✓[/green] {result['mission_yaml']}")
    console.print(f"[green]✓[/green] {result['agents_md']}")


@app.command()
def watch(
    mission_id: Optional[str] = typer.Option(None, "--mission", "-m"),
    interval: float = typer.Option(2.0, "--interval", "-i"),
) -> None:
    """Watch mission events in real time."""
    watch_events(mission_id, interval)


@app.command()
def dashboard(
    port: int = typer.Option(8765, "--port", "-p"),
) -> None:
    """Launch local web dashboard."""
    run_dashboard(port)


@app.command()
def bootstrap(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace path"
    ),
    write_rule: bool = typer.Option(
        True, "--write-rule/--no-write-rule", help="Refresh ~/.cursor/rules/ai-guider-session.mdc"
    ),
) -> None:
    """Print session bootstrap context (mission + map + act grant)."""
    from guider.hooks_runtime import build_bootstrap_context, write_session_rule

    data = build_bootstrap_context(str(workspace) if workspace else None)
    console.print(data["text"])
    if write_rule:
        path = write_session_rule(data["text"])
        console.print(f"\n[dim]Session rule updated: {path}[/dim]")


@app.command(name="hook")
def hook_cmd(
    event: str = typer.Argument("preToolUse", help="sessionStart or preToolUse"),
) -> None:
    """Cursor hook stdin/stdout adapter (used by hooks/*.sh)."""
    import sys

    sys.argv = ["ai-guider-hook", event]
    from guider.hooks_runtime import run_hook_stdin

    run_hook_stdin()


@app.command(name="map")
def map_cmd(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", "-w", help="Workspace path to map"
    ),
    max_depth: int = typer.Option(4, "--depth", "-d", help="Max directory depth"),
    as_json: bool = typer.Option(False, "--json", help="Print raw JSON"),
    refresh: bool = typer.Option(False, "--refresh", help="Bypass cache"),
) -> None:
    """Print a local codebase map (stdout only — does not write project files)."""
    svc = GuiderService()
    data = svc.map_codebase(
        str(workspace) if workspace else None,
        max_depth=max_depth,
        refresh=refresh,
    )
    if as_json:
        console.print_json(data=data)
        return

    summary = data.get("summary") or {}
    console.print(f"[cyan]Workspace[/cyan] {data.get('workspace')}")
    console.print(
        f"[cyan]Files[/cyan] {summary.get('file_count', 0)}  "
        f"[cyan]Dirs[/cyan] {summary.get('dir_count', 0)}  "
        f"[cyan]Cached[/cyan] {data.get('cached')}"
    )
    langs = summary.get("languages") or {}
    if langs:
        console.print("[cyan]Languages[/cyan] " + ", ".join(f"{k}={v}" for k, v in langs.items()))
    eps = data.get("entrypoints") or []
    if eps:
        console.print("\n[cyan]Entrypoints[/cyan]")
        for e in eps:
            console.print(f"  • {e}")
    mods = data.get("modules") or []
    if mods:
        console.print(f"\n[cyan]Modules with symbols[/cyan] ({len(mods)})")
        for m in mods[:15]:
            syms = ", ".join(
                f"{s['kind']}:{s['name']}" for s in (m.get("symbols") or [])[:5]
            )
            console.print(f"  • {m['path']}: {syms}")
    for hint in data.get("hints") or []:
        console.print(f"[dim]→ {hint}[/dim]")


@app.command()
def templates() -> None:
    """List available mission templates."""
    from guider.mission.templates import list_templates
    table = Table(title="Mission Templates")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Description")
    for t in list_templates():
        table.add_row(t["id"], t["name"], t["description"])
    console.print(table)


@app.command()
def missions(
    limit: int = typer.Option(20, "--limit", "-n", help="Max missions to show"),
) -> None:
    """List stored missions."""
    db = get_database()
    items = db.list_missions(limit=limit)

    if not items:
        console.print("[yellow]No missions found. Use govern_request via MCP to start.[/yellow]")
        return

    table = Table(title="Missions")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Confidence")
    table.add_column("Objective")

    for m in items:
        table.add_row(
            m.id,
            m.status.value,
            f"{m.confidence_score:.0%}",
            m.objective[:60] + ("..." if len(m.objective) > 60 else ""),
        )

    console.print(table)


@app.command(name="config")
def show_config(
    show: bool = typer.Option(True, "--show/--edit", help="Show current configuration"),
) -> None:
    """Show current AI Guider configuration."""
    cfg = get_config()
    if show:
        console.print_json(data=cfg.to_dict())


@app.command(hidden=True)
def serve() -> None:
    """Explicitly run the MCP server (same as running ai-guider with no args)."""
    run_server()


if __name__ == "__main__":
    app()
