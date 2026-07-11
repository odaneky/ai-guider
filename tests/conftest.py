"""Test configuration."""

import os
from pathlib import Path

import pytest
import yaml

from guider.config.loader import GuiderConfig
from guider.storage.database import Database, reset_database_singleton


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test.db"
    return Database(db_path)


@pytest.fixture
def config() -> GuiderConfig:
    return GuiderConfig(profile="balanced")


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AI Guider config + DB at a temp dir (no ~/.ai-guider writes)."""
    reset_database_singleton()
    config_path = tmp_path / "config.yaml"
    db_path = tmp_path / "guider.db"
    config_path.write_text(
        yaml.dump(
            {
                "profile": "balanced",
                "database_path": str(db_path),
                "plugins": ["personal"],
                "validators": {
                    "scope": {"enabled": True},
                    "assumptions": {"enabled": True},
                    "completion": {"enabled": True},
                    "consistency": {"enabled": True},
                    "risk": {"enabled": True},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_GUIDER_CONFIG", str(config_path))
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_database_singleton()
