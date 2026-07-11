from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table

from guider.storage.database import get_database

console = Console()


def watch_events(mission_id: Optional[str] = None, interval: float = 2.0) -> None:
    """Tail mission events in the terminal."""
    db = get_database()
    seen: set[str] = set()

    def build_table() -> Table:
        table = Table(title="AI Guider — Event Watch")
        table.add_column("Time", style="dim")
        table.add_column("Mission", style="cyan")
        table.add_column("Event")
        table.add_column("Message")

        if mission_id:
            events = db.list_events(mission_id, limit=15)
        else:
            missions = db.list_missions(limit=5)
            events = []
            for m in missions:
                events.extend(db.list_events(m.id, limit=5))
            events.sort(key=lambda e: e.created_at, reverse=True)
            events = events[:15]

        for e in events:
            ts = e.created_at.strftime("%H:%M:%S")
            table.add_row(ts, e.mission_id[:14], e.event_type.value, e.message[:60])
        return table

    console.print("[dim]Watching events… Ctrl+C to stop[/dim]")
    try:
        with Live(build_table(), refresh_per_second=1, console=console) as live:
            while True:
                time.sleep(interval)
                live.update(build_table())
    except KeyboardInterrupt:
        console.print("\nStopped.")
