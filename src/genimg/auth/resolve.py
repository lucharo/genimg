"""Pick the auth profile for a run.

Order: `--profile NAME` → a mode forced by a flag (`--auth azure`) → the provider's profile
in config.toml (the single one, or the first declared when several) → env auto-detection
in the provider's declared mode order. No config and no env → a clear error naming the
env vars that would have worked.
"""
from __future__ import annotations

from typing import Any

from .. import config as _cfg
from .base import AuthInfo, AuthProfile, profile_from_table


def _provider(name: str):
  from ..providers import get
  return get(name)


def candidates(provider_name: str, cfg: dict[str, Any] | None = None) -> list[AuthProfile]:
  """Configured profiles for a provider, in declaration order."""
  provider = _provider(provider_name)
  out: list[AuthProfile] = []
  for name, table in _cfg.profiles_for(provider_name, cfg).items():
    try:
      out.append(profile_from_table(provider.modes, name, table))
    except ValueError:
      continue
  return out


def resolve(provider_name: str, *, profile_name: str | None = None, force_mode: str | None = None,
            cfg: dict[str, Any] | None = None) -> AuthProfile:
  """Return the profile to use, or raise RuntimeError with a fix-it hint."""
  provider = _provider(provider_name)
  cfg = _cfg.load() if cfg is None else cfg

  if profile_name is not None:
    table = _cfg.profiles(cfg).get(profile_name)
    if table is None:
      known = ", ".join(sorted(_cfg.profiles(cfg))) or "(none)"
      raise RuntimeError(f"no profile {profile_name!r} in {_cfg.CONFIG_PATH}. Known: {known}.")
    if table.get("provider") != provider_name:
      raise RuntimeError(
        f"profile {profile_name!r} is for provider {table.get('provider')!r}, "
        f"but the selected model needs {provider_name!r}."
      )
    return profile_from_table(provider.modes, profile_name, table)

  if force_mode is not None:
    cls = provider.modes.get(force_mode)
    if cls is None:
      raise RuntimeError(f"{provider_name} has no auth mode {force_mode!r}; choose {', '.join(provider.modes)}.")
    # Reuse settings from a configured profile of that mode, if any (e.g. the Azure endpoint).
    settings = next((p.settings for p in candidates(provider_name, cfg) if p.mode == force_mode), {})
    return cls(settings, source="flag")

  configured = candidates(provider_name, cfg)
  if configured:
    return configured[0]

  probes = [cls({}, source="env") for cls in provider.auth_modes]
  for probe in probes:
    if probe.detect():
      return probe

  env = sorted({v for cls in provider.auth_modes for v in cls.env_vars})
  if not env and len(probes) == 1:
    raise RuntimeError(probes[0].info().hint or f"No {provider_name} auth detected.")
  raise RuntimeError(
    f"No {provider_name} auth detected. Run `genimg setup`"
    + (f" or set {' / '.join(env)}." if env else ".")
  )


def info(provider_name: str, *, profile_name: str | None = None, force_mode: str | None = None,
         cfg: dict[str, Any] | None = None) -> AuthInfo:
  """Readiness snapshot; never raises. An unresolvable provider reports mode 'unset'."""
  try:
    profile = resolve(provider_name, profile_name=profile_name, force_mode=force_mode, cfg=cfg)
  except RuntimeError as e:
    return AuthInfo(mode="unset", source="-", endpoint="-", credential="-", ok=False, hint=str(e))
  return profile.info()


def all_info(cfg: dict[str, Any] | None = None) -> dict[str, AuthInfo]:
  from ..providers import all_providers
  cfg = _cfg.load() if cfg is None else cfg
  return {p.name: info(p.name, cfg=cfg) for p in all_providers()}
