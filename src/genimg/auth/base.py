"""Auth profiles: one class per (provider, auth mode).

A profile knows which env vars carry its secret, how to build an SDK client, how to run a
free live preflight, and how to describe its own readiness. Non-secret settings (GCP
project, Azure endpoint, region) come from a `[profiles.NAME]` table in config.toml;
secrets always come from the environment.

Providers declare their modes (`Provider.auth_modes`); `resolve()` picks one for a run.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class AuthInfo:
  """Readiness snapshot shown by `genimg auth` and the generate banner."""
  mode: str
  source: str            # "profile:NAME" | "flag" | "env" | "-"
  endpoint: str          # host, project or "-"
  credential: str        # env var name or a label; "-" when absent
  ok: bool
  hint: str = ""
  profile: str | None = None

  def as_dict(self) -> dict[str, Any]:
    return {"mode": self.mode, "source": self.source, "endpoint": self.endpoint,
            "credential": self.credential, "ok": self.ok, "hint": self.hint,
            "profile": self.profile}


@dataclass(frozen=True)
class SettingSpec:
  """A non-secret profile setting the setup wizard may ask for."""
  key: str
  prompt: str
  required: bool = False
  detect: Any = None  # callable () -> str | None, offers a default


@dataclass(frozen=True)
class SecretSpec:
  """A secret the wizard can guide the user to obtain (never stored in config)."""
  env_var: str
  label: str
  signup_url: str | None = None
  kind: str = "text"  # "text" | "path"


class AuthProfile(ABC):
  """Base for one provider auth mode. Subclasses set the class attributes and implement
  `detect`, `client`, `validate`, `info`."""

  provider: ClassVar[str]
  mode: ClassVar[str]
  label: ClassVar[str]
  env_vars: ClassVar[tuple[str, ...]] = ()
  secret: ClassVar[SecretSpec | None] = None
  settings_spec: ClassVar[tuple[SettingSpec, ...]] = ()

  def __init__(self, settings: dict[str, Any] | None = None, *, name: str | None = None,
               source: str = "env"):
    self.settings: dict[str, Any] = dict(settings or {})
    self.name = name
    self.source = source

  # ── contract ──
  @abstractmethod
  def detect(self) -> bool:
    """True when the credentials this mode needs are present (no network)."""

  @abstractmethod
  def client(self, **kw: Any) -> Any:
    """Build the provider SDK client."""

  @abstractmethod
  def validate(self) -> tuple[bool, str]:
    """Free live preflight (models.list or login status). Returns (ok, error)."""

  @abstractmethod
  def info(self) -> AuthInfo:
    """Readiness snapshot without network calls."""

  # ── helpers ──
  def detail(self) -> str:
    """One-line description for the setup wizard choice list."""
    found = self.present_env_var()
    if found:
      return f"{found}={_mask(os.getenv(found))} in env"
    return "needs " + " or ".join(self.env_vars) if self.env_vars else "not detected"

  def present_env_var(self) -> str | None:
    for var in self.env_vars:
      if os.getenv(var):
        return var
    return None

  def __repr__(self) -> str:
    return f"<{type(self).__name__} name={self.name!r} source={self.source!r}>"


def _mask(value: str | None, n: int = 3) -> str:
  if not value:
    return ""
  return value[:n] + "…"


def profile_from_table(modes: dict[str, type[AuthProfile]], name: str, table: dict[str, Any]) -> AuthProfile:
  """Instantiate a profile from a `[profiles.NAME]` table."""
  mode = table.get("auth")
  cls = modes.get(mode or "")
  if cls is None:
    raise ValueError(
      f"profile {name!r}: unknown auth mode {mode!r} for provider {table.get('provider')!r}; "
      f"choose one of {', '.join(sorted(modes))}"
    )
  settings = {k: v for k, v in table.items() if k not in ("provider", "auth")}
  return cls(settings, name=name, source=f"profile:{name}")


__all__ = ["AuthInfo", "AuthProfile", "SecretSpec", "SettingSpec", "profile_from_table"]
