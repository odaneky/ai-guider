"""User preference / decision library."""

from __future__ import annotations

from typing import Dict, List, Optional

from guider.storage.database import Database


class PreferenceStore:
    """Persist and recall user decisions across missions."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, key: str, value: str, reason: str = "") -> None:
        self.db.set_preference(key, value, reason)

    def get(self, key: str) -> Optional[Dict[str, str]]:
        return self.db.get_preference(key)

    def list_all(self) -> List[Dict[str, str]]:
        return self.db.list_preferences()

    def apply_to_mission_context(self) -> str:
        """Build context string from saved preferences."""
        prefs = self.list_all()
        if not prefs:
            return ""
        lines = ["Known user preferences:"]
        for p in prefs:
            lines.append(f"- {p['key']}: {p['value']}")
        return "\n".join(lines)

    def suggest_for_unknown(self, unknown: str) -> Optional[str]:
        """Suggest a preference value for a matching unknown."""
        key_map = {
            "technology stack": "tech_stack",
            "database": "database",
            "data storage": "database",
            "authentication": "auth",
            "deployment environment": "deployment",
        }
        pref_key = key_map.get(unknown.lower())
        if pref_key:
            pref = self.get(pref_key)
            if pref:
                return pref["value"]
        return None
