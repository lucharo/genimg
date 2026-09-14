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

The pre-0.1.0 JSON config (`config.json`, `enabled_providers`) is migrated on first load.
"""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

CONFIG_DIR = Path(os.getenv("GENIMG_CONFIG_HOME") or Path.home() / ".config" / "genimg")
CONFIG_PATH = CONFIG_DIR / "config.toml"
LEGACY_JSON_PATH = CONFIG_DIR / "config.json"

# Legacy `enabled_providers` entries → (provider, auth mode, profile name).
_LEGACY_MODES = {
  "google_direct":     ("google", "direct"),
  "google_vertex":     ("google", "vertex"),
  "google_vertex_adc": ("google", "vertex_adc"),
  "openai_native":     ("openai", "native"),
  "openai_direct":     ("openai", "native"),
  "openai_azure":      ("openai", "azure"),
  "codex":             ("codex", "subscription"),
}


def migrate_legacy(data: dict[str, Any]) -> dict[str, Any]:
  """Convert a config.json dict (enabled_providers + flat settings) to the TOML schema."""
  out: dict[str, Any] = {}
  for key in ("default_model", "default_quality", "default_aspect_ratio", "default_resolution"):
    if data.get(key) is not None:
      out[key] = data[key]
  profiles: dict[str, dict[str, Any]] = {}
  for entry in data.get("enabled_providers", []) or []:
    spec = _LEGACY_MODES.get(entry)
    if spec is None:
      continue
    provider, mode = spec
    table: dict[str, Any] = {"provider": provider, "auth": mode}
    if provider == "google" and mode != "direct":
      if data.get("gcp_project"):
        table["project"] = data["gcp_project"]
      if data.get("gcp_region"):
        table["region"] = data["gcp_region"]
    if provider == "openai" and mode == "azure":
      if data.get("openai_base_url"):
        table["endpoint"] = data["openai_base_url"]
      if data.get("azure_api_version"):
        table["api_version"] = data["azure_api_version"]
    profiles[provider] = table
  if profiles:
    out["profiles"] = profiles
  return out


def _read_toml(path: Path) -> dict[str, Any]:
  try:
    return tomllib.loads(path.read_text())
  except (tomllib.TOMLDecodeError, OSError):
    return {}


def load() -> dict[str, Any]:
  """Load config.toml. If only the legacy config.json exists, migrate it in place."""
  if CONFIG_PATH.exists():
    return _read_toml(CONFIG_PATH)
  if LEGACY_JSON_PATH.exists():
    try:
      legacy = json.loads(LEGACY_JSON_PATH.read_text())
    except (json.JSONDecodeError, OSError):
      return {}
    data = migrate_legacy(legacy if isinstance(legacy, dict) else {})
    try:
      save(data)
      LEGACY_JSON_PATH.rename(LEGACY_JSON_PATH.with_suffix(".json.migrated"))
    except OSError:
      pass
    return data
  return {}


def save(data: dict[str, Any]) -> None:
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  clean = {k: v for k, v in data.items() if v is not None}
  CONFIG_PATH.write_text(tomli_w.dumps(clean))


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


def open_in_editor() -> None:
  """Open the config file in $EDITOR (creating it if needed)."""
  import subprocess
  editor = os.getenv("EDITOR") or "vi"
  CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
  CONFIG_PATH.touch(exist_ok=True)
  subprocess.run([editor, str(CONFIG_PATH)])
