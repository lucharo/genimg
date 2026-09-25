"""`genimg setup` wizard. Detect → fetch → validate → save (per provider).

Goals: feel automatic, never save a broken state. For each registered provider the wizard
offers its auth modes with live detection, guides the user to any missing secret (opens the
signup page, prompts, optionally writes `export VAR=...` to the shell rc), asks for the
mode's non-secret settings, runs the mode's free preflight, and only then writes the
provider's `[profiles.NAME]` table to config.toml (its configured one, else NAME = provider).

Without a terminal on stdin (an agent, CI) it never prompts: each provider's detected auth
mode is validated and saved, and nothing is fetched or written to a shell rc.
"""
from __future__ import annotations

import os
import shlex
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable

import questionary
from rich.console import Console
from rich.markup import escape

from . import config, providers, registry
from .auth.base import AuthProfile, SecretSpec

console = Console()


# ────────────────────── helpers ──────────────────────

def _profile_line(name: str, table: dict) -> str:
  """One summary line per saved profile. Escaped, or Rich reads `[profiles.x]` as a style tag and drops it."""
  extras = ", ".join(f"{k}={v}" for k, v in table.items() if k not in ("provider", "auth"))
  return escape(f"  [profiles.{name}] {table['provider']} / {table['auth']}" + (f"  ({extras})" if extras else ""))


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


def _validate(validate_fn: Callable[[], tuple[bool, str]]) -> tuple[bool, str]:
  """The mode's free preflight. An SDK client that raises while it is built (a malformed Azure
  endpoint, say) is a failed validation, not a crash that discards the other providers."""
  try:
    return validate_fn()
  except Exception as e:  # noqa: BLE001 — reported as this provider's failure
    return False, f"{type(e).__name__}: {e}"


def _run_validation(label: str, validate_fn: Callable[[], tuple[bool, str]]) -> bool:
  """Run a live validation; allow retry/skip/cancel on failure."""
  while True:
    with console.status(f"validating {label}..."):
      ok, err = _validate(validate_fn)
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

def _detect_modes(provider: providers.Provider, cfg: dict[str, Any]):
  """(profile name, candidates, detected-by-mode, saved table) for the profile runs use: the
  provider's first declared profile, as auth resolution picks it, else one named after the
  provider. The saved mode is seeded with its settings and counts as detected when its secret is
  in env: a saved direct OpenAI profile works with an Azure endpoint in env, which env
  auto-detection alone reads as an Azure setup. No network."""
  name, existing = next(iter(config.profiles_for(provider.name, cfg).items()), (provider.name, None))
  saved_mode = existing.get("auth") if existing else None
  saved_settings = {k: v for k, v in (existing or {}).items() if k not in ("provider", "auth")}
  candidates = [cls(saved_settings if cls.mode == saved_mode else {}, name=name, source=f"profile:{name}")
                for cls in provider.auth_modes]
  detected = {p.mode: p.detect() or (p.mode == saved_mode and p.present_env_var() is not None)
              for p in candidates}
  return name, candidates, detected, existing


def _setup_provider(provider: providers.Provider, cfg: dict[str, Any]) -> bool:
  """Offer the provider's auth modes; save a validated table under the provider's configured
  profile name (see _detect_modes). Returns True when a profile was saved."""
  profiles = cfg.setdefault("profiles", {})
  console.print(f"\n[bold cyan]{provider.label}[/bold cyan]")
  name, candidates, detected, existing = _detect_modes(provider, cfg)

  if len(candidates) == 1 and not candidates[0].env_vars and not candidates[0].secret:
    # Login-style providers (Codex): nothing to fetch, just opt in.
    p = candidates[0]
    if not detected[p.mode]:
      _forget_provider(provider.name, name, cfg)
      console.print(f"[dim]{provider.label}: {p.detail()}[/dim]")
      return False
    use = questionary.confirm(f"Use {provider.label}?", default=existing is not None).ask()
    if not use:
      _forget_provider(provider.name, name, cfg)
      return False
    profiles[name] = {"provider": provider.name, "auth": p.mode}
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
  profiles[name] = {"provider": provider.name, "auth": chosen.mode, **chosen.settings}
  return True


def _setup_provider_unattended(provider: providers.Provider, cfg: dict[str, Any]) -> tuple[bool, str]:
  """No prompts: save the first detected auth mode whose free validation passes (the saved
  profile's mode first, then the wizard's order). Returns (saved, summary)."""
  name, candidates, detected, existing = _detect_modes(provider, cfg)
  ordered = sorted(candidates, key=lambda p: not (existing and existing.get("auth") == p.mode))
  found = [p for p in ordered if detected[p.mode]]
  if not found:
    login_style = len(candidates) == 1 and not candidates[0].env_vars  # Codex: its hint says how
    if login_style:
      _forget_provider(provider.name, name, cfg)  # as the wizard does for a logged-out Codex
    why = candidates[0].detail() if login_style else "`genimg auth --modes` lists the env vars"
    return False, f"skipped: no credentials detected ({why})"
  failures = []
  for chosen in found:
    # Required settings may come from env detection; optional ones stay to runtime resolution
    # (a Vertex project from gcloud must not override the service-account JSON's).
    for setting in chosen.settings_spec:
      value = chosen.settings.get(setting.key) or (setting.detect() if setting.required and setting.detect else None)
      if value:
        chosen.settings[setting.key] = value
    missing = [s.key for s in chosen.settings_spec if s.required and not chosen.settings.get(s.key)]
    if missing:
      failures.append(f"{chosen.label} needs `{missing[0]}`")
      continue
    ok, err = _validate(chosen.validate)
    if ok:
      cfg.setdefault("profiles", {})[name] = {"provider": provider.name, "auth": chosen.mode, **chosen.settings}
      return True, f"saved ({chosen.mode})"
    failures.append(f"{chosen.label} validation failed: {err}")
  return False, "skipped: " + "; ".join(failures)


def _forget_provider(provider: str, name: str, cfg: dict[str, Any]) -> None:
  """Drop profile `name`, and the default model once no profile covers its provider."""
  profiles = cfg.get("profiles") or {}
  profiles.pop(name, None)
  if not profiles:
    cfg.pop("profiles", None)
  default = cfg.get("default_model")
  if default and not config.profiles_for(provider, cfg):
    try:
      if registry.resolve(default)[1].provider == provider:
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

def _interactive() -> bool:
  return sys.stdin.isatty()


def run_setup(model: str | None = None) -> bool:
  """`model` (a registry alias) becomes the default instead of asking for one. Returns False
  when an unattended run (no terminal on stdin) validated no provider, or when no profile
  covers `model`'s provider so it could not be saved."""
  if not _interactive():
    return _run_unattended(model)
  console.print("[bold cyan]genimg setup[/bold cyan] — detect → fetch → validate → save")
  cfg = config.load()

  saved: list[str] = []
  try:
    for provider in providers.all_providers():
      if _setup_provider(provider, cfg):
        saved.append(provider.name)
  except KeyboardInterrupt:
    console.print("\n[yellow]cancelled — config not saved[/yellow]")
    return True

  if not cfg.get("profiles"):
    config.save(cfg)
    console.print("\n[yellow]No providers configured.[/yellow] Re-run when ready.")
    return _set_default_model(cfg, model) if model else True  # a requested default was not saved

  if model:
    default_saved = _set_default_model(cfg, model)
  else:
    default_saved = True
    try:
      _setup_default_model(cfg)
    except KeyboardInterrupt:
      pass  # skipping the default is fine; providers are already validated

  config.save(cfg)
  _print_saved(cfg)
  return default_saved


def _set_default_model(cfg: dict[str, Any], model: str) -> bool:
  """Save `model` as the default only when a profile covers its provider, as the picker does."""
  provider = registry.resolve(model)[1].provider
  if provider not in {t.get("provider") for t in (cfg.get("profiles") or {}).values() if isinstance(t, dict)}:
    console.print(f"[yellow]default model not saved:[/yellow] {model} needs a {provider} profile, and there is none.")
    return False
  cfg["default_model"] = model
  return True


def _run_unattended(model: str | None) -> bool:
  """Never prompts, never takes a secret, never writes a shell rc: the human puts keys in the
  environment, the agent runs setup."""
  console.print("[bold cyan]genimg setup[/bold cyan] — no terminal: detect → validate → save, no prompts")
  cfg = config.load()
  results = [(provider.label, *_setup_provider_unattended(provider, cfg))
             for provider in providers.all_providers()]
  for label, _, summary in results:
    console.print(f"  {label}: {escape(summary)}", soft_wrap=True)
  if not any(saved for _, saved, _ in results):
    console.print("\n[yellow]No provider validated; config not changed.[/yellow] Put a key in the "
                  "environment (`genimg auth --modes` lists them), then re-run.")
    return False
  default_saved = _set_default_model(cfg, model) if model else True
  config.save(cfg)
  _print_saved(cfg)
  return default_saved


def _print_saved(cfg: dict[str, Any]) -> None:
  console.print(f"\n[green]saved[/green] {config.CONFIG_PATH}", soft_wrap=True)
  for name, table in cfg["profiles"].items():
    console.print(_profile_line(name, table))
  if cfg.get("default_model"):
    console.print(f"  default model: {cfg['default_model']}")
  configured = [t["provider"] for t in cfg["profiles"].values()]
  test_model = ("" if cfg.get("default_model")
                else " -m codex:image" if configured == ["codex"]
                else " -m gdm:nb2" if "google" in configured
                else " -m oai:gi2")
  console.print(f"\n[dim]inspect: `genimg auth`  •  test: `genimg \"a robot\"{test_model} -o /tmp/r.png`[/dim]")
