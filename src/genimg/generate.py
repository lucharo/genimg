"""High-level dispatch: registry lookup → provider → auth profile → generate."""
from __future__ import annotations

from .auth.base import AuthProfile
from .auth.resolve import resolve as resolve_profile
from .interfaces import GenerateRequest, GenerateResult
from .providers import get as get_provider
from .registry import resolve


def generate(req: GenerateRequest, *, profile: str | None = None, auth_mode: str | None = None) -> GenerateResult:
  """Resolve req.model (alias or canonical), pick the auth profile, dispatch to the provider.

  `profile` names a `[profiles.NAME]` table; `auth_mode` forces one of the provider's modes
  (the CLI's `--auth`).
  """
  _, spec = resolve(req.model)
  provider = get_provider(spec.provider)
  if auth_mode is not None and auth_mode not in provider.modes:
    raise ValueError(f"{spec.provider} has no auth mode {auth_mode!r}; choose {', '.join(provider.modes)}")
  # Resolve eagerly only when the caller pinned a profile or mode; otherwise the provider's
  # client factory resolves lazily (config profile → env) at the first API call.
  auth: AuthProfile | None = (resolve_profile(spec.provider, profile_name=profile, force_mode=auth_mode)
                              if profile is not None or auth_mode is not None else None)
  resolved_req = req.model_copy(update={
    "model": spec.model_id,
    "region": req.region or spec.region,
  })
  return provider.make(auth).generate(resolved_req)
