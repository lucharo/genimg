"""User config (~/.config/genimg/config.json). Currently: default model alias."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.getenv("GENIMG_CONFIG_HOME") or Path.home() / ".config" / "genimg") / "config.json"


def load() -> dict[str, Any]:
  if not CONFIG_PATH.exists():
    return {}
  try:
    return json.loads(CONFIG_PATH.read_text())
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
