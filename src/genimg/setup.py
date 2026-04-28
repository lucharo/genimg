"""Interactive `genimg setup` wizard. Detect → confirm → optionally probe → save."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import questionary
from rich.console import Console

from . import config

console = Console()

_DETECTED_VARS = (
  "CLAUDE_GCP_CRED",
  "GOOGLE_APPLICATION_CREDENTIALS",
  "GEMINI_API_KEY",
  "GOOGLE_API_KEY",
  "OPENAI_API_KEY",
  "OPENAI_BASE_URL",
  "AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_API_KEY",
)


def _detect_env() -> dict[str, str]:
  return {k: v for k in _DETECTED_VARS if (v := os.getenv(k))}


def _detect_gcloud() -> tuple[str | None, str | None]:
  if not shutil.which("gcloud"):
    return None, None
  try:
    project = subprocess.run(
      ["gcloud", "config", "get-value", "project"], capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    region = subprocess.run(
      ["gcloud", "config", "get-value", "compute/region"], capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    return (project or None), (region or None)
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return None, None


def _truncate(s: str, n: int = 60) -> str:
  return s if len(s) <= n else s[: n - 3] + "..."


def run_setup() -> None:
  console.print("[bold cyan]genimg setup[/bold cyan] — quick onboarding\n")

  # 1. Detect env vars
  env = _detect_env()
  console.print(f"[dim]detected {len(env)} relevant env var(s)[/dim]")
  accepted_env: dict[str, str] = {}
  for var, value in env.items():
    use = questionary.confirm(
      f"Use {var}={_truncate(value)} ?", default=True,
    ).ask()
    if use is None:  # ctrl-c
      console.print("[yellow]cancelled[/yellow]")
      return
    if use:
      accepted_env[var] = value

  # 2. gcloud detection
  proj, region = _detect_gcloud()
  use_gcloud_proj, use_gcloud_region = None, None
  if proj:
    use_gcloud_proj = questionary.confirm(
      f"gcloud says project={proj}. Use that for Vertex?", default=True,
    ).ask()
  if region:
    use_gcloud_region = questionary.confirm(
      f"gcloud says region={region}. Use that?", default=True,
    ).ask()

  # 3. Multi-select providers
  has_vertex_creds = "CLAUDE_GCP_CRED" in accepted_env or "GOOGLE_APPLICATION_CREDENTIALS" in accepted_env
  has_google_direct = "GEMINI_API_KEY" in accepted_env or "GOOGLE_API_KEY" in accepted_env
  has_azure = (
    "AZURE_OPENAI_ENDPOINT" in accepted_env
    or "azure" in accepted_env.get("OPENAI_BASE_URL", "").lower()
  )
  has_openai_direct = "OPENAI_API_KEY" in accepted_env and not has_azure

  choices = [
    questionary.Choice("Google (Vertex)", checked=has_vertex_creds, value="google_vertex"),
    questionary.Choice("Google (direct API)", checked=has_google_direct, value="google_direct"),
    questionary.Choice("OpenAI (Azure)", checked=has_azure, value="openai_azure"),
    questionary.Choice("OpenAI (direct)", checked=has_openai_direct, value="openai_direct"),
  ]
  enabled = questionary.checkbox(
    "Enable which providers? (space to toggle, enter to confirm)", choices=choices,
  ).ask()
  if enabled is None:
    console.print("[yellow]cancelled[/yellow]")
    return

  # 4. Optional live probe
  do_probe = questionary.confirm(
    "Probe which models you actually have access to right now?", default=False,
  ).ask()

  # 5. Save config
  cfg = config.load()
  cfg["enabled_providers"] = enabled
  if use_gcloud_proj and proj:
    cfg["gcp_project"] = proj
  if use_gcloud_region and region:
    cfg["gcp_region"] = region
  cfg["accepted_env"] = list(accepted_env.keys())
  config.save(cfg)
  console.print(f"\n[green]saved[/green] {config.CONFIG_PATH}")
  console.print(f"  enabled: {', '.join(enabled) or '(none)'}")
  if cfg.get("gcp_project"):
    console.print(f"  gcp project: {cfg['gcp_project']}")

  # 6. Probe (after save so config influences default model selection)
  if do_probe:
    console.print("\n[dim]probing...[/dim]")
    from . import discovery
    from .cli import _list_models  # reuse
    _list_models(refresh=True, show_aliases=False)
