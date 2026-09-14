"""Interactive `genimg setup` wizard. Detect → fetch → validate → save (per provider).

Goals: feel automatic, never save a broken state. For each registered provider the wizard
offers its auth modes with live detection, guides the user to any missing secret (opens the
signup page, prompts, optionally writes `export VAR=...` to the shell rc), asks for the
mode's non-secret settings, runs the mode's free preflight, and only then writes a
`[profiles.<provider>]` table to config.toml.
"""
from __future__ import annotations

import os
import shlex
import webbrowser
from pathlib import Path
from typing import Any, Callable

import questionary
from rich.console import Console

from . import config, providers, registry
from .auth.base import AuthProfile, SecretSpec

console = Console()


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


def _open_signup(url: str | None) -> None:
  if not url:
    return
  if _is_remote():
    console.print(f"[dim]Open in your browser: {url}[/dim]")
  else:
    console.print(f"[dim]Opening {url}...[/dim]")
    webbrowser.open(url)


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


def _persist(var: str, value: str, *, prompt: str) -> None:
  persist = questionary.confirm(prompt, default=True).ask()
  if persist:
    _append_export(var, value)
  else:
    os.environ[var] = value
    console.print("[dim]session-only — won't persist after this terminal closes[/dim]")


def _fetch_secret(secret: SecretSpec) -> bool:
  """Open the signup page, prompt for the value, optionally write it to the shell rc.
  Returns True iff captured."""
  if secret.kind == "path":
    console.print(f"[dim]{secret.label} needed.[/dim]")
    _open_signup(secret.signup_url)
    raw = questionary.path(f"Path to {secret.label} (or empty to skip):").ask()
    if not raw:
      return False
    p = Path(raw).expanduser()
    if not p.exists():
      console.print(f"[red]not found: {p}[/red]")
      return False
    _persist(secret.env_var, str(p), prompt=f"Save `export {secret.env_var}={p}` to your shell rc?")
    return True
  console.print(f"[dim]No {secret.env_var} found. Get one:[/dim]")
  _open_signup(secret.signup_url)
  val = questionary.password(f"Paste your {secret.label} (or empty to skip):").ask()
  if not val:
    return False
  _persist(secret.env_var, val, prompt=f"Save `export {secret.env_var}=...` to your shell rc? (no = session-only)")
  return True


def _choice_label(text: str, ok: bool, detail: str) -> str:
  """Plain-text choice label: `✓ Name  ·  detail` or `✗ Name  ·  what's missing`."""
  icon = "✓" if ok else "✗"
  return f"{icon}  {text}  ·  {detail}"


# ────────────────────── per-provider step ──────────────────────

def _setup_provider(provider: providers.Provider, cfg: dict[str, Any]) -> bool:
  """Offer the provider's auth modes; save a validated `[profiles.<provider>]` table.
  Returns True when a profile was saved."""
  profiles = cfg.setdefault("profiles", {})
  existing = profiles.get(provider.name) if isinstance(profiles.get(provider.name), dict) else None
  existing_settings = {k: v for k, v in (existing or {}).items() if k not in ("provider", "auth")}
  console.print(f"\n[bold cyan]{provider.label}[/bold cyan]")

  candidates = [cls(existing_settings if existing and existing.get("auth") == cls.mode else {},
                    name=provider.name, source=f"profile:{provider.name}")
                for cls in provider.auth_modes]
  detected = {p.mode: p.detect() for p in candidates}

  if len(candidates) == 1 and not candidates[0].env_vars and not candidates[0].secret:
    # Login-style providers (Codex): nothing to fetch, just opt in.
    p = candidates[0]
    if not detected[p.mode]:
      _forget_provider(provider.name, cfg)
      console.print(f"[dim]{provider.label}: {p.detail()}[/dim]")
      return False
    use = questionary.confirm(f"Use {provider.label}?", default=existing is not None).ask()
    if not use:
      _forget_provider(provider.name, cfg)
      return False
    profiles[provider.name] = {"provider": provider.name, "auth": p.mode}
    return True

  pick = questionary.select(
    f"Pick a {provider.label} auth path (or skip):",
    choices=[
      *[questionary.Choice(_choice_label(p.label, detected[p.mode], p.detail()), value=p.mode) for p in candidates],
      questionary.Choice(f"Skip {provider.label}", value="skip"),
    ],
  ).ask()
  if pick in (None, "skip"):
    return False
  chosen: AuthProfile = next(p for p in candidates if p.mode == pick)

  if not detected[pick]:
    if chosen.secret is not None:
      if not _fetch_secret(chosen.secret):
        return False
    else:
      console.print(f"[yellow]{chosen.label}: {chosen.detail()} — then re-run `genimg setup`.[/yellow]")
      return False

  for setting in chosen.settings_spec:
    current = chosen.settings.get(setting.key)
    default = current or (setting.detect() if setting.detect else None) or ""
    if setting.required and not default and setting.key == "endpoint":
      console.print()
      console.print("[dim]Azure needs the resource endpoint URL — looks like:[/dim] [bold]https://<resource>.openai.azure.com[/bold]")
      console.print("[dim]Find it in: Azure portal → your OpenAI resource → 'Keys and Endpoint'.[/dim]")
    value = questionary.text(setting.prompt, default=str(default)).ask()
    if value is None:
      raise KeyboardInterrupt
    value = value.strip()
    if value:
      chosen.settings[setting.key] = value
    elif setting.required:
      console.print(f"[red]{setting.key} is required for {chosen.label}.[/red]")
      return False
    else:
      chosen.settings.pop(setting.key, None)

  if not _run_validation(provider.label, chosen.validate):
    return False
  profiles[provider.name] = {"provider": provider.name, "auth": chosen.mode, **chosen.settings}
  return True


def _forget_provider(name: str, cfg: dict[str, Any]) -> None:
  profiles = cfg.get("profiles") or {}
  profiles.pop(name, None)
  if not profiles:
    cfg.pop("profiles", None)
  default = cfg.get("default_model")
  if default:
    try:
      if registry.resolve(default)[1].provider == name:
        cfg.pop("default_model")
    except ValueError:
      pass


# ────────────────────── default model ──────────────────────

def _setup_default_model(cfg: dict[str, Any]) -> None:
  """Offer to set a default model so `genimg PROMPT` works without -m (ADR 0001).

  There is no hardcoded default; the user picks from the models their configured
  profiles cover, or skips and passes -m each run.
  """
  configured = {t.get("provider") for t in (cfg.get("profiles") or {}).values() if isinstance(t, dict)}
  models = [
    (alias, spec)
    for alias, spec in sorted(
      registry.all_canonical().items(),
      key=lambda kv: (kv[1].provider, -kv[1].quality_rank, kv[0]),
    )
    if spec.provider in configured
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
    if cfg.pop("default_model", None):
      console.print("[dim]default model cleared — pass -m each run.[/dim]")
    return
  cfg["default_model"] = pick
  console.print(f"[green]default model →[/green] {pick}")


# ────────────────────── entry point ──────────────────────

def run_setup() -> None:
  console.print("[bold cyan]genimg setup[/bold cyan] — detect → fetch → validate → save")
  cfg = config.load()

  saved: list[str] = []
  try:
    for provider in providers.all_providers():
      if _setup_provider(provider, cfg):
        saved.append(provider.name)
  except KeyboardInterrupt:
    console.print("\n[yellow]cancelled — config not saved[/yellow]")
    return

  if not cfg.get("profiles"):
    config.save(cfg)
    console.print("\n[yellow]No providers configured.[/yellow] Re-run when ready.")
    return

  try:
    _setup_default_model(cfg)
  except KeyboardInterrupt:
    pass  # skipping the default is fine; providers are already validated

  config.save(cfg)
  console.print(f"\n[green]saved[/green] {config.CONFIG_PATH}")
  for name, table in cfg["profiles"].items():
    extras = ", ".join(f"{k}={v}" for k, v in table.items() if k not in ("provider", "auth"))
    console.print(f"  [profiles.{name}] {table['provider']} / {table['auth']}" + (f"  ({extras})" if extras else ""))
  if cfg.get("default_model"):
    console.print(f"  default model: {cfg['default_model']}")
  configured = [t["provider"] for t in cfg["profiles"].values()]
  test_model = ("" if cfg.get("default_model")
                else " -m codex:image" if configured == ["codex"]
                else " -m gdm:nb2" if "google" in configured
                else " -m oai:gi2")
  console.print(f"\n[dim]inspect: `genimg auth`  •  test: `genimg \"a robot\"{test_model} -o /tmp/r.png`[/dim]")
