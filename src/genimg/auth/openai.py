"""OpenAI client factory. Config wins (`genimg setup`), env is fallback.

Two modes:
  openai_native — OPENAI_API_KEY → api.openai.com  (was: openai_direct, auto-migrated)
  openai_azure  — Azure resource: api key + endpoint (OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT)
"""
from __future__ import annotations

import os

from openai import AzureOpenAI, OpenAI

from .. import config as _cfg

DEFAULT_AZURE_API_VERSION = "2025-04-01-preview"


def is_azure() -> bool:
  base = os.getenv("OPENAI_BASE_URL", "")
  return "azure.com" in base.lower() or os.getenv("AZURE_OPENAI_ENDPOINT") is not None


def _azure() -> AzureOpenAI:
  cfg = _cfg.load()
  endpoint = cfg.get("openai_base_url") or os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
  if not endpoint:
    raise RuntimeError(
      "Azure mode requires an endpoint. Set OPENAI_BASE_URL / AZURE_OPENAI_ENDPOINT, "
      "or save it via `genimg setup`."
    )
  api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
  if not api_key:
    raise RuntimeError("Azure mode requires OPENAI_API_KEY (or AZURE_OPENAI_API_KEY).")
  api_version = cfg.get("azure_api_version") or os.getenv("OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
  return AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)


def _direct(*, ignore_base_url: bool = False) -> OpenAI:
  """Direct OpenAI client. With ignore_base_url=True, force api.openai.com (used by --auth direct
  to guarantee bypass of any Azure/proxy URL set in OPENAI_BASE_URL)."""
  api_key = os.getenv("OPENAI_API_KEY")
  if not api_key:
    raise RuntimeError("Direct OpenAI mode requires OPENAI_API_KEY.")
  if ignore_base_url:
    return OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
  return OpenAI()  # honors OPENAI_BASE_URL for non-Azure proxies (LiteLLM, OpenRouter, ...)


def get_client(*, force: str | None = None) -> OpenAI | AzureOpenAI:
  """Return OpenAI or AzureOpenAI client. Resolution: --auth flag → saved config → env."""
  if force == "azure":
    return _azure()
  if force == "direct":
    return _direct(ignore_base_url=True)

  enabled = _cfg.load().get("enabled_providers", [])
  if "openai_azure" in enabled:
    return _azure()
  if "openai_native" in enabled:
    # User explicitly chose api.openai.com — bypass any OPENAI_BASE_URL proxy.
    return _direct(ignore_base_url=True)

  return _azure() if is_azure() else _direct()


def validate(mode: str, *, endpoint: str | None = None) -> tuple[bool, str]:
  """Live preflight via `client.models.list()` — free, no image generated.

  Returns (ok, error_msg). `mode` ∈ {openai_native, openai_azure}. `endpoint` overrides
  the saved/env endpoint — used by the setup wizard to preview a not-yet-saved value.
  """
  try:
    if mode == "openai_native":
      if not os.getenv("OPENAI_API_KEY"):
        return False, "OPENAI_API_KEY not in env"
      client = _direct(ignore_base_url=True)
    elif mode == "openai_azure":
      cfg = _cfg.load()
      ep = endpoint or cfg.get("openai_base_url") or os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
      if not ep:
        return False, "no endpoint (OPENAI_BASE_URL / AZURE_OPENAI_ENDPOINT / config.openai_base_url)"
      api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
      if not api_key:
        return False, "no api key (AZURE_OPENAI_API_KEY / OPENAI_API_KEY)"
      api_version = cfg.get("azure_api_version") or os.getenv("OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
      client = AzureOpenAI(api_key=api_key, azure_endpoint=ep, api_version=api_version)
    else:
      return False, f"unknown mode: {mode}"
    next(iter(client.models.list()), None)
    return True, ""
  except Exception as e:
    return False, f"{type(e).__name__}: {str(e)[:300]}"


def auth_info() -> dict[str, object]:
  """Structured auth status: {mode, source, endpoint, credential, ok, hint}.

  Azure mode requires BOTH an endpoint (config or env) and an api key. `ok` is False
  when either is missing — surfaces the failure at audit time instead of at request time.
  """
  cfg = _cfg.load()
  enabled = cfg.get("enabled_providers", [])
  in_config = "openai_azure" in enabled or "openai_native" in enabled
  source = "config" if in_config else "env"

  if "openai_azure" in enabled or (not in_config and is_azure()):
    endpoint = cfg.get("openai_base_url") or os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
    has_key = bool(os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
    cred = (
      "AZURE_OPENAI_API_KEY" if os.getenv("AZURE_OPENAI_API_KEY")
      else "OPENAI_API_KEY" if os.getenv("OPENAI_API_KEY")
      else "-"
    )
    ok = bool(endpoint) and has_key
    missing = []
    if not endpoint:
      missing.append("endpoint (OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT)")
    if not has_key:
      missing.append("api key (AZURE_OPENAI_API_KEY or OPENAI_API_KEY)")
    hint = "" if ok else (
      "Azure mode needs " + " and ".join(missing)
      + ". Run `genimg setup` to fix, or set in env."
    )
    return {
      "mode": "azure", "source": source,
      "endpoint": endpoint or "-",
      "credential": cred,
      "ok": ok, "hint": hint,
    }
  if "openai_native" in enabled or (not in_config and os.getenv("OPENAI_API_KEY")):
    ok = bool(os.getenv("OPENAI_API_KEY"))
    return {
      "mode": "native", "source": source,
      "endpoint": os.getenv("OPENAI_BASE_URL") or "https://api.openai.com",
      "credential": "OPENAI_API_KEY" if ok else "-",
      "ok": ok,
      "hint": "" if ok else "Native mode needs OPENAI_API_KEY in env.",
    }
  return {
    "mode": "unset", "source": "-", "endpoint": "-", "credential": "-",
    "ok": False,
    "hint": "Run `genimg setup` or set OPENAI_API_KEY (native) or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY (Azure).",
  }


def auth_mode() -> str:
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
