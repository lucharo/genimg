"""Interactive `genimg setup` wizard. Detect → fetch → validate → save (per provider).

Goals: feel automatic, never save a broken state. Hierarchical detection per provider;
guided fetch flow opens the right signup page, prompts for the value, optionally writes
`export VAR=...` to the user's shell rc. Live `client.models.list()` preflight before save.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable

import questionary
from rich.console import Console

from . import config
from .auth import google as auth_google
from .auth import openai as auth_openai

console = Console()

_SIGNUP_URLS = {
  "gemini": "https://aistudio.google.com/apikey",
  "openai": "https://platform.openai.com/api-keys",
  "azure":  "https://portal.azure.com/#create/Microsoft.CognitiveServicesOpenAI",
  "vertex_sa": "https://console.cloud.google.com/iam-admin/serviceaccounts",
}


# ────────────────────── helpers ──────────────────────

def _is_remote() -> bool:
  return bool(os.getenv("SSH_CONNECTION") or os.getenv("SSH_CLIENT"))


def _shell_rc_path() -> Path | None:
  shell = os.getenv("SHELL", "")
  home = Path.home()
  if "fish" in shell:
    rc = home / ".config" / "fish" / "config.fish"
    rc.parent.mkdir(parents=True, exist_ok=True)
    return rc
  if "zsh" in shell or (home / ".zshrc").exists():
    return home / ".zshrc"
  if "bash" in shell or (home / ".bashrc").exists():
    return home / ".bashrc"
  return None


def _format_export(rc: Path, var: str, value: str) -> str:
  return f"set -gx {var} {value}\n" if rc.name == "config.fish" else f"export {var}={value}\n"


def _has_export(text: str, var: str) -> bool:
  return any(
    line.lstrip().startswith(f"export {var}=") or line.lstrip().startswith(f"set -gx {var} ")
    for line in text.splitlines()
  )


def _append_export(var: str, value: str) -> Path | None:
  """Append `export VAR=value` to the user's shell rc (idempotent). Sets os.environ too.

  If a different value already exists for VAR in the rc, leave it alone (don't clobber).
  """
  os.environ[var] = value
  rc = _shell_rc_path()
  if rc is None:
    console.print(f"[yellow]couldn't detect shell rc — set this yourself:[/yellow]  export {var}=...")
    return None
  rc.touch(exist_ok=True)
  text = rc.read_text() if rc.exists() else ""
  if _has_export(text, var):
    console.print(f"[yellow]{rc.name} already exports {var} — left untouched (edit if it needs updating).[/yellow]")
    return rc
  with rc.open("a") as f:
    f.write(_format_export(rc, var, value))
  console.print(f"[green]added {var} to {rc}[/green]  [dim](active this session; new shells: source it)[/dim]")
  return rc


def _open_signup(name: str) -> None:
  url = _SIGNUP_URLS.get(name)
  if not url:
    return
  if _is_remote():
    console.print(f"[dim]Open in your browser: {url}[/dim]")
  else:
    console.print(f"[dim]Opening {url}...[/dim]")
    webbrowser.open(url)


def _detected_gcp_project() -> str | None:
  if not shutil.which("gcloud"):
    return None
  try:
    r = subprocess.run(
      ["gcloud", "config", "get-value", "project"],
      capture_output=True, text=True, timeout=5,
    )
    return r.stdout.strip() or None
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return None


def _run_validation(label: str, validate_fn: Callable[[], tuple[bool, str]]) -> bool:
  """Run a live validation; allow retry/skip/cancel on failure."""
  while True:
    with console.status(f"validating {label}..."):
      ok, err = validate_fn()
    if ok:
      console.print(f"[green]✓ {label} validated[/green]")
      return True
    console.print(f"[red]✗ {label} validation failed:[/red] {err}")
    choice = questionary.select(
      "What now?",
      choices=["Retry", "Skip this provider", "Cancel setup"],
    ).ask()
    if choice in (None, "Cancel setup"):
      raise KeyboardInterrupt
    if choice == "Skip this provider":
      return False


def _fetch_secret(provider_url_key: str, var: str, label: str) -> bool:
  """Open signup page, prompt for value, optionally write to shell rc. Returns True iff captured."""
  console.print(f"[dim]No {var} found. Get one:[/dim]")
  _open_signup(provider_url_key)
  val = questionary.password(f"Paste your {label} (or empty to skip):").ask()
  if not val:
    return False
  persist = questionary.confirm(
    f"Save `export {var}=...` to your shell rc? (no = session-only)",
    default=True,
  ).ask()
  if persist:
    _append_export(var, val)
  else:
    os.environ[var] = val
    console.print(f"[dim]session-only — won't persist after this terminal closes[/dim]")
  return True


def _fetch_sa_json() -> bool:
  console.print("[dim]Vertex needs a service-account JSON.[/dim]")
  _open_signup("vertex_sa")
  raw = questionary.path("Path to service-account JSON (or empty to skip):").ask()
  if not raw:
    return False
  p = Path(raw).expanduser()
  if not p.exists():
    console.print(f"[red]not found: {p}[/red]")
    return False
  persist = questionary.confirm(
    f"Save `export GOOGLE_APPLICATION_CREDENTIALS={p}` to your shell rc?", default=True,
  ).ask()
  if persist:
    _append_export("GOOGLE_APPLICATION_CREDENTIALS", str(p))
  else:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p)
  return True


def _choice_label(text: str, ready: bool, missing: str) -> str:
  """Plain-text label for questionary (no Rich markup — questionary won't parse it)."""
  return f"{text}  ·  {'ready' if ready else missing}"


# ────────────────────── per-provider steps ──────────────────────

def _setup_google(cfg: dict) -> bool:
  has_direct = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
  has_sa = bool(os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
  has_adc = auth_google.adc_token_present()

  console.print("\n[bold cyan]Google[/bold cyan] (Gemini Image / Imagen)")
  detected = []
  if has_direct: detected.append("Gemini API key")
  if has_sa: detected.append("Vertex SA JSON")
  if has_adc: detected.append("gcloud ADC")
  if detected:
    console.print(f"  [dim]detected:[/dim] {', '.join(detected)}")
  else:
    console.print("  [dim]nothing detected[/dim]")

  pick = questionary.select(
    "Pick a Google auth path (or skip):",
    choices=[
      questionary.Choice(_choice_label("Direct API (Gemini key)", has_direct, "needs key"), value="google_direct"),
      questionary.Choice(_choice_label("Vertex (service account JSON)", has_sa, "needs JSON"), value="google_vertex"),
      questionary.Choice(_choice_label("Vertex (gcloud user creds, ADC)", has_adc, "needs gcloud login"), value="google_vertex_adc"),
      questionary.Choice("Skip Google", value="skip"),
    ],
  ).ask()
  if pick in (None, "skip"):
    return False

  if pick == "google_direct" and not has_direct:
    if not _fetch_secret("gemini", "GEMINI_API_KEY", "Gemini API key"):
      return False
  elif pick == "google_vertex" and not has_sa:
    if not _fetch_sa_json():
      return False
  elif pick == "google_vertex_adc" and not has_adc:
    console.print("[yellow]ADC needs a one-time login. Run this in another terminal, then re-run `genimg setup`:[/yellow]")
    console.print("  [bold]gcloud auth application-default login[/bold]")
    return False

  if pick in ("google_vertex", "google_vertex_adc"):
    detected_proj = _detected_gcp_project() or cfg.get("gcp_project")
    proj = questionary.text(
      "GCP project ID for Vertex (leave empty for SDK default):",
      default=detected_proj or "",
    ).ask()
    if proj:
      cfg["gcp_project"] = proj

  enabled = cfg.setdefault("enabled_providers", [])
  for other in ("google_direct", "google_vertex", "google_vertex_adc"):
    if other != pick and other in enabled:
      enabled.remove(other)
  if pick not in enabled:
    enabled.append(pick)

  ok = _run_validation("Google", lambda: auth_google.validate(mode=pick, project=cfg.get("gcp_project")))
  if not ok:
    enabled.remove(pick)
    return False
  return True


def _setup_openai(cfg: dict) -> bool:
  has_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"))
  env_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or (
    os.getenv("OPENAI_BASE_URL") if "azure" in os.getenv("OPENAI_BASE_URL", "").lower() else None
  )
  cfg_endpoint = cfg.get("openai_base_url")
  has_azure_endpoint = bool(env_endpoint or cfg_endpoint)

  console.print("\n[bold cyan]OpenAI[/bold cyan] (gpt-image-*)")
  detected = []
  if has_key: detected.append("API key")
  if has_azure_endpoint: detected.append("Azure endpoint")
  if detected:
    console.print(f"  [dim]detected:[/dim] {', '.join(detected)}")
  else:
    console.print("  [dim]nothing detected[/dim]")

  native_ready = has_key and not env_endpoint  # OPENAI_BASE_URL not pointing at Azure
  azure_ready = has_key and has_azure_endpoint

  pick = questionary.select(
    "Pick an OpenAI auth path (or skip):",
    choices=[
      questionary.Choice(_choice_label("OpenAI native (api.openai.com)", native_ready, "needs OPENAI_API_KEY"), value="openai_native"),
      questionary.Choice(_choice_label("OpenAI via Azure", azure_ready, "needs key + endpoint"), value="openai_azure"),
      questionary.Choice("Skip OpenAI", value="skip"),
    ],
  ).ask()
  if pick in (None, "skip"):
    return False

  if pick == "openai_native" and not os.getenv("OPENAI_API_KEY"):
    if not _fetch_secret("openai", "OPENAI_API_KEY", "OpenAI API key"):
      return False

  if pick == "openai_azure":
    if not has_key:
      if not _fetch_secret("azure", "AZURE_OPENAI_API_KEY", "Azure OpenAI API key"):
        return False
    if not has_azure_endpoint:
      url = questionary.text(
        "Azure resource endpoint (e.g. https://my-resource.openai.azure.com):",
      ).ask()
      if not url:
        return False
      cfg["openai_base_url"] = url.strip()

  enabled = cfg.setdefault("enabled_providers", [])
  for other in ("openai_native", "openai_azure"):
    if other != pick and other in enabled:
      enabled.remove(other)
  if pick not in enabled:
    enabled.append(pick)

  ok = _run_validation(
    "OpenAI",
    lambda: auth_openai.validate(mode=pick, endpoint=cfg.get("openai_base_url")),
  )
  if not ok:
    enabled.remove(pick)
    if pick == "openai_azure" and not env_endpoint:
      cfg.pop("openai_base_url", None)
    return False
  return True


# ────────────────────── entry point ──────────────────────

def run_setup() -> None:
  console.print("[bold cyan]genimg setup[/bold cyan] — detect → fetch → validate → save\n")
  cfg = config.load()

  try:
    google_ok = _setup_google(cfg)
    openai_ok = _setup_openai(cfg)
  except KeyboardInterrupt:
    console.print("\n[yellow]cancelled — config not saved[/yellow]")
    return

  if not (google_ok or openai_ok):
    console.print("\n[yellow]No providers enabled.[/yellow] Re-run when ready.")
    return

  config.save(cfg)
  console.print(f"\n[green]saved[/green] {config.CONFIG_PATH}")
  console.print(f"  enabled: {', '.join(cfg.get('enabled_providers', [])) or '(none)'}")
  if cfg.get("gcp_project"):
    console.print(f"  gcp project: {cfg['gcp_project']}")
  if cfg.get("openai_base_url"):
    console.print(f"  openai base url: {cfg['openai_base_url']}")
  console.print("\n[dim]inspect: `genimg auth`  •  test: `genimg \"a robot\" -o /tmp/r.png`[/dim]")
