from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_DIR = Path.home() / ".ai-guider"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "guider.db"


class ValidatorConfig(BaseModel):
    enabled: bool = True


class ValidatorsConfig(BaseModel):
    scope: ValidatorConfig = Field(default_factory=ValidatorConfig)
    assumptions: ValidatorConfig = Field(default_factory=ValidatorConfig)
    completion: ValidatorConfig = Field(default_factory=ValidatorConfig)
    consistency: ValidatorConfig = Field(default_factory=ValidatorConfig)
    risk: ValidatorConfig = Field(default_factory=ValidatorConfig)


class RulesConfig(BaseModel):
    require_mission_for: List[str] = Field(
        default_factory=lambda: ["coding", "architecture", "research"]
    )
    min_confidence_threshold: float = 0.70
    min_scope_score: int = 60
    caution_scope_max: int = 75
    completion_stop_score: int = 100
    require_user_confirmation: bool = True
    scope_max_files: int = 20


class HooksConfig(BaseModel):
    enforce_act: bool = True
    grant_ttl_seconds: int = 1800
    write_session_rule: bool = True


class GuiderConfig(BaseModel):
    profile: str = "balanced"
    rules: RulesConfig = Field(default_factory=RulesConfig)
    validators: ValidatorsConfig = Field(default_factory=ValidatorsConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    database_path: str = str(DEFAULT_DB_PATH)
    plugins: List[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuiderConfig":
        return cls.model_validate(data)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


DEFAULT_CONFIG_YAML = """profile: balanced

rules:
  require_mission_for:
    - coding
    - architecture
    - research
  min_confidence_threshold: 0.70
  min_scope_score: 60
  caution_scope_max: 75
  completion_stop_score: 100
  require_user_confirmation: true
  scope_max_files: 20

validators:
  scope:
    enabled: true
  assumptions:
    enabled: true
  completion:
    enabled: true
  consistency:
    enabled: true
  risk:
    enabled: true

plugins:
  - personal

hooks:
  enforce_act: true
  grant_ttl_seconds: 1800
  write_session_rule: true
"""


def get_config_path() -> Path:
    env_path = os.environ.get("AI_GUIDER_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_PATH


def init_config(path: Optional[Path] = None) -> Path:
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return config_path


def get_config(path: Optional[Path] = None) -> GuiderConfig:
    config_path = path or get_config_path()
    if not config_path.exists():
        init_config(config_path)
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return GuiderConfig.from_dict(data)
