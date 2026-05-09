"""User config at ~/.config/genimg/config.json.

Schema (all optional, additive):
  enabled_providers: list[str]      # {google_direct, google_vertex, google_vertex_adc, openai_native, openai_azure}
  default_model:     str            # alias or canonical id
  gcp_project:       str            # for Vertex modes
  gcp_region:        str            # for Vertex modes
  openai_base_url:   str            # Azure resource URL or proxy (non-secret)
  azure_api_version: str            # optional override for Azure api-version

Secrets (API keys, service-account JSON paths) live in env, never here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.getenv("GENIMG_CONFIG_HOME") or Path.home() / ".config" / "genimg") / "config.json"


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
  """Read-time renames. Mutates the dict in place. Re-saved lazily on next setup."""
  enabled = data.get("enabled_providers")
  if isinstance(enabled, list) and "openai_direct" in enabled:
    data["enabled_providers"] = ["openai_native" if e == "openai_direct" else e for e in enabled]
  return data


def load() -> dict[str, Any]:
  if not CONFIG_PATH.exists():
    return {}
  try:
    return _migrate(json.loads(CONFIG_PATH.read_text()))
  except (json.JSONDecodeError, OSError):
    return {}


def save(data: dict[str, Any]) -> None:
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  CONFIG_PATH.write_text(json.dumps(data, indent=2))


def get_default_model() -> str | None:
  return load().get("default_model")


def set_default_model(alias: str) -> None:
  data = load()
  data["default_model"] = alias
  save(data)


def clear_default_model() -> None:
  data = load()
  data.pop("default_model", None)
  save(data)


def open_in_editor() -> None:
  """Open the config file in $EDITOR (creating it if needed)."""
  import os
  import subprocess
  editor = os.getenv("EDITOR") or "vi"
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  CONFIG_PATH.touch(exist_ok=True)
  subprocess.run([editor, str(CONFIG_PATH)])
