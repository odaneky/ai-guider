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

COMMAND_GUIDE = """
[bold]AI Guider — command guide[/bold]

Local MCP governance for AI coding agents. Guider does not write your code;
it helps agents clarify scope, ask you questions, and finish cleanly.

[bold cyan]Getting started[/bold cyan]
  ai-guider help                 Show this full guide
  ai-guider --help               Short command list
  ai-guider <command> --help     Flags and options for one command
  ai-guider doctor               Check that install + clients look healthy
  ai-guider init --all-clients   Wire Cursor, Claude Code, Desktop, and Codex

[bold cyan]Setup & clients[/bold cyan]
  [green]init[/green]         Create config/DB and connect AI clients (MCP)
                --all-clients       Cursor+hooks, Claude Code, Desktop, Codex
                --cursor --hooks    Cursor IDE + session/edit guardrails
                --claude            Claude Code (~/.claude.json)
                --claude-desktop    Claude Desktop app
                --codex             OpenAI Codex (~/.codex/config.toml)
                --project-mcp DIR   Write project .mcp.json (Claude Code)
                --config PATH       Alternate config file
  [green]doctor[/green]       Health checks (Python, config, MCP wiring, hooks)
  [green]config[/green]       Print current configuration as JSON
  [green]status[/green]       Runtime stats (missions, events, pending questions)

[bold cyan]Missions (day to day)[/bold cyan]
  [green]resume[/green]       Active mission, pending questions, recent events
                -w / --workspace    Force workspace path
  [green]missions[/green]     List stored missions
                -n / --limit N      How many to show (default 20)
  [green]templates[/green]    List mission templates (personal-site, API, …)
  [green]report[/green]       Governance compliance summary (JSON)
                -m / --mission ID   Limit to one mission
  [green]export[/green]       Write .ai-guider/mission.yaml + AGENTS.md into a project
                ai-guider export <mission_id> <project_dir>
  [green]watch[/green]        Stream mission events in the terminal
                -m / --mission ID   -i / --interval SECONDS
  [green]dashboard[/green]    Local web UI for missions
                -p / --port PORT    Default 8765

[bold cyan]Codebase & Cursor[/bold cyan]
  [green]map[/green]          Local codebase map (tree, entrypoints, symbols)
                -w / --workspace    Project root (default: cwd)
                -d / --depth N      Max directory depth (default 4)
                --json              Raw JSON output
                --refresh           Bypass cache
  [green]bootstrap[/green]    Session briefing (mission + map + act grant)
                -w / --workspace
                --no-write-rule     Do not update ~/.cursor/rules/ai-guider-session.mdc
  [green]hook[/green]         Cursor hook adapter (used by hooks/*.sh — not for daily use)
                ai-guider hook sessionStart | preToolUse

[bold cyan]MCP server[/bold cyan]
  ai-guider                      (no subcommand) Start the MCP server for Cursor/Claude/Codex

[bold cyan]Typical first-time flow[/bold cyan]
  1. pip install ai-guider   (or editable install from a git clone)
  2. ai-guider init --all-clients
  3. Restart / reload your AI client
  4. ai-guider doctor
  5. In the agent chat: ask it to use AI Guider (govern_request, …)

[dim]Docs: https://github.com/odaneky/ai-guider — see docs/installation.md and docs/usage.md[/dim]
""".strip()

app = typer.Typer(
    name="ai-guider",
    help=(
        "AI Guider — local-first MCP governance for AI coding agents.\n\n"
        "Run [bold]ai-guider help[/bold] for a full command guide, "
        "or [bold]ai-guider <command> --help[/bold] for flags."
    ),
    no_args_is_help=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="Examples:  ai-guider help  ·  ai-guider init --all-clients  ·  ai-guider doctor",
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run MCP server when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        run_server()


@app.command("help")
def help_command(
    command: Optional[str] = typer.Argument(
        None,
        help="Optional command name to show detailed flag help (e.g. init, map)",
    ),
) -> None:
    """Show a comprehensive guide to all commands (or detailed help for one command)."""
    if command:
        from typer.main import get_command

        click_cmd = get_command(app)
        sub = click_cmd.commands.get(command)
        if sub is None:
            console.print(f"[red]Unknown command:[/red] {command}")
            console.print("Run [cyan]ai-guider help[/cyan] for the full list.")
            raise typer.Exit(1)
        ctx = typer.Context(sub, info_name=command, parent=typer.Context(click_cmd))
        console.print(sub.get_help(ctx))
        return

    console.print(COMMAND_GUIDE)


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
        False,
        "--all-clients",
        help="Configure Cursor+hooks, Claude Code, Claude Desktop, and Codex in one step",
    ),
    project_mcp: Optional[Path] = typer.Option(
        None,
        "--project-mcp",
        help="Also write .mcp.json into this project directory (Claude Code project scope)",
    ),
) -> None:
    """Create local config/database and optionally wire MCP clients.

    Examples:

        ai-guider init --all-clients

        ai-guider init --cursor --hooks

        ai-guider init --claude --codex

        ai-guider init --project-mcp .
    """
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
    """Show runtime status (profile, DB path, mission counts)."""
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
    """Show the active mission, pending questions, and recent events."""
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
    """Run health checks on config, Python, MCP clients, and Cursor hooks."""
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
    """Show a governance compliance report as JSON."""
    data = governance_report(get_database(), mission_id)
    console.print_json(data=data)


@app.command()
def export(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    project_path: Path = typer.Argument(..., help="Project directory"),
) -> None:
    """Export a mission into the project as .ai-guider/mission.yaml and AGENTS.md."""
    svc = GuiderService()
    result = svc.export_mission(mission_id, str(project_path))
    console.print(f"[green]✓[/green] {result['mission_yaml']}")
    console.print(f"[green]✓[/green] {result['agents_md']}")


@app.command()
def watch(
    mission_id: Optional[str] = typer.Option(None, "--mission", "-m"),
    interval: float = typer.Option(2.0, "--interval", "-i"),
) -> None:
    """Watch mission events in real time in the terminal."""
    watch_events(mission_id, interval)


@app.command()
def dashboard(
    port: int = typer.Option(8765, "--port", "-p"),
) -> None:
    """Launch the local web dashboard for missions."""
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
    """Print session bootstrap context (active mission, map hints, act grant)."""
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
    """Cursor hook stdin/stdout adapter (used by hooks/*.sh; not for daily use)."""
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
    """Print a local codebase map (stdout only — does not write project files).

    Examples:

        ai-guider map

        ai-guider map --workspace . --json

        ai-guider map --refresh
    """
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
    """List available mission templates (personal-site, API, and more)."""
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
    """List stored missions (id, status, confidence, objective)."""
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
    """Show the current AI Guider configuration as JSON."""
    cfg = get_config()
    if show:
        console.print_json(data=cfg.to_dict())


@app.command(hidden=True)
def serve() -> None:
    """Explicitly run the MCP server (same as running ai-guider with no args)."""
    run_server()


if __name__ == "__main__":
    app()
