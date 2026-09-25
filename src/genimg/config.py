"""User config at ~/.config/genimg/config.toml.

Schema (all optional):

  default_model        = "gdm:nb2"      # alias or canonical id
  default_quality      = "medium"       # OpenAI-only — low | medium | high | auto | xhigh | max
  default_aspect_ratio = "16:9"         # model-dependent; see `genimg -h`
  default_resolution   = "2K"           # 512 | 1K | 2K | 4K (model-dependent)

  [profiles.NAME]                       # one table per auth profile; NAME is yours
  provider = "google"                   # google | openai | codex
  auth     = "vertex_adc"               # a mode of that provider (see `genimg auth --modes`)
  project  = "my-gcp-project"           # non-secret settings the mode understands
  region   = "global"

Secrets (API keys, service-account JSON paths) live in env, never here. A profile is
selected with `--profile NAME`; with one profile per provider it is picked automatically.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

CONFIG_DIR = Path(os.getenv("GENIMG_CONFIG_HOME") or Path.home() / ".config" / "genimg")
CONFIG_PATH = CONFIG_DIR / "config.toml"


class ConfigError(RuntimeError):
  """config.toml exists but cannot be parsed; genimg refuses to read or overwrite it."""


def _read_toml(path: Path) -> dict[str, Any]:
  try:
    return tomllib.loads(path.read_text())
  except OSError:
    return {}
  except tomllib.TOMLDecodeError as e:
    raise ConfigError(f"{path} is not valid TOML ({e}). Fix it or move it aside; genimg will not overwrite it.") from e


def load() -> dict[str, Any]:
  """Load config.toml; a missing file is an empty config."""
  if CONFIG_PATH.exists():
    return _read_toml(CONFIG_PATH)
  return {}


def save(data: dict[str, Any]) -> None:
  """Atomic write. A config that currently fails to parse is never overwritten (see load)."""
  if CONFIG_PATH.exists():
    _read_toml(CONFIG_PATH)  # raises ConfigError on a corrupt file instead of clobbering it
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  clean = {k: v for k, v in data.items() if v is not None}
  tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
  tmp.write_text(tomli_w.dumps(clean))
  os.replace(tmp, CONFIG_PATH)


def dumps(data: dict[str, Any]) -> str:
  return tomli_w.dumps({k: v for k, v in data.items() if v is not None})


# ── profiles ──

def profiles(data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
  data = load() if data is None else data
  raw = data.get("profiles") or {}
  return {name: table for name, table in raw.items() if isinstance(table, dict)}


def profiles_for(provider: str, data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
  return {n: t for n, t in profiles(data).items() if t.get("provider") == provider}


def set_profile(name: str, table: dict[str, Any]) -> None:
  data = load()
  data.setdefault("profiles", {})[name] = table
  save(data)


def remove_profile(name: str) -> bool:
  data = load()
  removed = data.get("profiles", {}).pop(name, None) is not None
  if removed:
    if not data["profiles"]:
      data.pop("profiles")
    save(data)
  return removed


# ── default model ──

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


def _editor_command(editor: str, *, windows: bool = os.name == "nt") -> list[str]:
  """$EDITOR as argv. It is a command line (EDITOR="code --wait"), unless it names an existing file
  (a path with spaces). Windows splits without POSIX escapes, so C:\\...\\notepad.exe keeps its
  backslashes, and drops the quotes around a quoted path."""
  import shlex
  if os.path.isfile(editor):
    return [editor]
  if windows:
    return [part.strip('"') for part in shlex.split(editor, posix=False)]
  return shlex.split(editor)


def open_in_editor() -> None:
  """Open the config file in $EDITOR (creating it if needed)."""
  import subprocess
  editor = _editor_command(os.getenv("EDITOR") or "") or ["vi"]
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  CONFIG_PATH.touch(exist_ok=True)
  subprocess.run([*editor, str(CONFIG_PATH)])
