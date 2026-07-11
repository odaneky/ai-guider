from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import urlparse

from guider.reporting import governance_report
from guider.storage.database import get_database


def _dashboard_html() -> str:
    db = get_database()
    stats = db.get_stats()
    missions = db.list_missions(limit=20)
    rows = "".join(
        f"<tr><td>{m.id}</td><td>{m.status.value}</td>"
        f"<td>{m.confidence_score:.0%}</td><td>{m.objective[:50]}</td></tr>"
        for m in missions
    )
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>AI Guider Dashboard</title>
<style>
  body {{ font-family: system-ui; margin: 2rem; background: #f7f5f2; color: #1a1210; }}
  h1 {{ font-weight: 500; }}
  .stats {{ display: flex; gap: 1rem; margin: 1.5rem 0; }}
  .stat {{ background: #fff; padding: 1rem 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .stat strong {{ font-size: 1.5rem; display: block; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; }}
  th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
</style>
</head><body>
<h1>AI Guider Dashboard</h1>
<div class="stats">
  <div class="stat"><strong>{stats['missions']}</strong>Missions</div>
  <div class="stat"><strong>{stats['active_missions']}</strong>Active</div>
  <div class="stat"><strong>{stats['pending_questions']}</strong>Pending Questions</div>
  <div class="stat"><strong>{stats['decisions']}</strong>Decisions</div>
</div>
<table>
  <tr><th>ID</th><th>Status</th><th>Confidence</th><th>Objective</th></tr>
  {rows or '<tr><td colspan="4">No missions yet</td></tr>'}
</table>
<p style="color:#888;font-size:13px;margin-top:2rem">Local only · Refresh to update</p>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/report" and "?" in self.path:
            mission_id = self.path.split("mission_id=")[-1]
            data = governance_report(get_database(), mission_id)
            body = json.dumps(data, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        body = _dashboard_html().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass


def run_dashboard(port: int = 8765) -> None:
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"AI Guider dashboard: http://127.0.0.1:{port}")
    server.serve_forever()
