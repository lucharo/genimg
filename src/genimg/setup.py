"""Interactive `genimg setup` wizard. Detect → fetch → validate → save (per provider).

Goals: feel automatic, never save a broken state. Hierarchical detection per provider;
guided fetch flow opens the right signup page, prompts for the value, optionally writes
`export VAR=...` to the user's shell rc. Live `client.models.list()` preflight before save.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable

import questionary
from rich.console import Console

from . import config, registry
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
  """Format a persistent export line, properly escaping `value` for the target shell."""
  if rc.name == "config.fish":
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"set -gx {var} '{escaped}'\n"
  return f"export {var}={shlex.quote(value)}\n"


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
    console.print("[dim]session-only — won't persist after this terminal closes[/dim]")
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


def _mask(value: str | None, n: int = 3) -> str:
  """Show the first n chars of a secret-ish value, then ellipsis. Empty → ''."""
  if not value:
    return ""
  return value[:n] + "…"


def _host(url: str | None) -> str:
  """Compact URL for display (host portion only)."""
  if not url:
    return ""
  from urllib.parse import urlparse
  parsed = urlparse(url)
  return parsed.netloc or url


def _choice_label(text: str, ok: bool, detail: str) -> str:
  """Plain-text choice label: `✓ Name  ·  detail` or `✗ Name  ·  what's missing`."""
  icon = "✓" if ok else "✗"
  return f"{icon}  {text}  ·  {detail}"


# ────────────────────── per-provider steps ──────────────────────

def _setup_google(cfg: dict) -> bool:
  has_direct = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
  has_sa = bool(os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
  has_adc = auth_google.adc_token_present()

  console.print("[bold cyan]Google[/bold cyan] (Gemini Image / Imagen)")

  direct_detail = (
    f"GEMINI_API_KEY={_mask(os.getenv('GEMINI_API_KEY'))} in env" if os.getenv("GEMINI_API_KEY")
    else f"GOOGLE_API_KEY={_mask(os.getenv('GOOGLE_API_KEY'))} in env" if os.getenv("GOOGLE_API_KEY")
    else "needs GEMINI_API_KEY or GOOGLE_API_KEY"
  )
  sa_detail = (
    f"CLAUDE_GCP_CRED={_mask(os.getenv('CLAUDE_GCP_CRED'))} in env" if os.getenv("CLAUDE_GCP_CRED")
    else f"GOOGLE_APPLICATION_CREDENTIALS set ({_host(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))})" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    else "needs CLAUDE_GCP_CRED or GOOGLE_APPLICATION_CREDENTIALS"
  )
  adc_detail = "gcloud token active" if has_adc else "run `gcloud auth application-default login`"

  pick = questionary.select(
    "Pick a Google auth path (or skip):",
    choices=[
      questionary.Choice(_choice_label("Direct API (Gemini key)", has_direct, direct_detail), value="google_direct"),
      questionary.Choice(_choice_label("Vertex (service account JSON)", has_sa, sa_detail), value="google_vertex"),
      questionary.Choice(_choice_label("Vertex (gcloud user creds, ADC)", has_adc, adc_detail), value="google_vertex_adc"),
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

  native_ready = bool(os.getenv("OPENAI_API_KEY")) and not env_endpoint
  azure_ready = has_key and has_azure_endpoint

  if os.getenv("OPENAI_API_KEY"):
    native_detail = f"OPENAI_API_KEY={_mask(os.getenv('OPENAI_API_KEY'))} in env"
  else:
    native_detail = "needs OPENAI_API_KEY"

  azure_key_var = (
    "AZURE_OPENAI_API_KEY" if os.getenv("AZURE_OPENAI_API_KEY")
    else "OPENAI_API_KEY" if os.getenv("OPENAI_API_KEY")
    else None
  )
  azure_endpoint_str = env_endpoint or cfg_endpoint
  if azure_ready:
    azure_detail = (
      f"{azure_key_var}={_mask(os.getenv(azure_key_var))}, "
      f"endpoint {_host(azure_endpoint_str)}"
    )
  elif has_key and not has_azure_endpoint:
    azure_detail = f"key {azure_key_var}={_mask(os.getenv(azure_key_var))} OK, endpoint missing"
  elif has_azure_endpoint and not has_key:
    azure_detail = f"endpoint {_host(azure_endpoint_str)} OK, key missing"
  else:
    azure_detail = "needs api key + resource endpoint"

  pick = questionary.select(
    "Pick an OpenAI auth path (or skip):",
    choices=[
      questionary.Choice(_choice_label("OpenAI native (api.openai.com)", native_ready, native_detail), value="openai_native"),
      questionary.Choice(_choice_label("OpenAI via Azure", azure_ready, azure_detail), value="openai_azure"),
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
      console.print()
      console.print("[dim]Azure needs the resource endpoint URL — looks like:[/dim] [bold]https://<resource>.openai.azure.com[/bold]")
      console.print("[dim]Find it in: Azure portal → your OpenAI resource → 'Keys and Endpoint'.[/dim]")
      console.print("[dim]Or copy from an existing config (codex/config.toml, litellm, etc.) — same URL, different env-var name.[/dim]")
      url = questionary.text("Paste the URL:").ask()
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


# ────────────────────── default model ──────────────────────

def _setup_default_model(cfg: dict) -> None:
  """Offer to set a default model so `genimg PROMPT` works without -m (ADR 0001).

  There is no hardcoded default; the user picks from the models their enabled
  providers cover, or skips and passes -m each run.
  """
  enabled = cfg.get("enabled_providers", [])
  providers = {p for e in enabled for p in ("google", "openai") if e.startswith(p)}
  models = [
    (alias, spec)
    for alias, spec in sorted(
      registry.all_canonical().items(),
      key=lambda kv: (kv[1].provider, -kv[1].quality_rank, kv[0]),
    )
    if spec.provider in providers
  ]
  if not models:
    return
  current = cfg.get("default_model")
  choices = [
    questionary.Choice(f"{alias}  ({spec.provider} / {spec.model_id})", value=alias)
    for alias, spec in models
  ]
  # Sentinel (not None) so an explicit Skip is distinguishable from a Ctrl-C cancel.
  skip = "\0skip"
  choices.append(questionary.Choice("Skip (pass -m each run)", value=skip))
  prompt = "Default model for `genimg PROMPT` (used when you omit -m)?"
  if current:
    prompt += f"  [current: {current}]"
  pick = questionary.select(prompt, choices=choices).ask()
  if pick is None:
    return  # cancelled — leave config untouched
  if pick == skip:
    # Explicit "pass -m each run": drop any stale default (e.g. for a provider just disabled).
    if cfg.pop("default_model", None):
      console.print("[dim]default model cleared — pass -m each run.[/dim]")
    return
  cfg["default_model"] = pick
  console.print(f"[green]default model →[/green] {pick}")


# ────────────────────── entry point ──────────────────────

def run_setup() -> None:
  console.print("[bold cyan]genimg setup[/bold cyan] — detect → fetch → validate → save")
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

  try:
    _setup_default_model(cfg)
  except KeyboardInterrupt:
    pass  # skipping the default is fine; providers are already validated

  config.save(cfg)
  console.print(f"\n[green]saved[/green] {config.CONFIG_PATH}")
  console.print(f"  enabled: {', '.join(cfg.get('enabled_providers', [])) or '(none)'}")
  if cfg.get("default_model"):
    console.print(f"  default model: {cfg['default_model']}")
  if cfg.get("gcp_project"):
    console.print(f"  gcp project: {cfg['gcp_project']}")
  if cfg.get("openai_base_url"):
    console.print(f"  openai base url: {cfg['openai_base_url']}")
  test_model = "" if cfg.get("default_model") else " -m gdm:nb"
  console.print(f"\n[dim]inspect: `genimg auth`  •  test: `genimg \"a robot\"{test_model} -o /tmp/r.png`[/dim]")
