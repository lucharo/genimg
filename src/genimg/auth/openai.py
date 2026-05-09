"""OpenAI client factory. Config wins (`genimg setup`), env is fallback."""
from __future__ import annotations

import os

from openai import AzureOpenAI, OpenAI

from .. import config as _cfg

DEFAULT_AZURE_API_VERSION = "2025-04-01-preview"


def is_azure() -> bool:
  base = os.getenv("OPENAI_BASE_URL", "")
  return "azure.com" in base.lower() or os.getenv("AZURE_OPENAI_ENDPOINT") is not None


def _azure() -> AzureOpenAI:
  endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
  if not endpoint:
    raise RuntimeError("Azure mode requires OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT.")
  api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
  if not api_key:
    raise RuntimeError("Azure mode requires OPENAI_API_KEY (or AZURE_OPENAI_API_KEY).")
  api_version = os.getenv("OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
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
    return _direct(ignore_base_url=True)  # explicit bypass of OPENAI_BASE_URL

  enabled = _cfg.load().get("enabled_providers", [])
  if "openai_azure" in enabled:
    return _azure()
  if "openai_direct" in enabled:
    return _direct()

  # No config preference → env auto-detection
  return _azure() if is_azure() else _direct()


def auth_info() -> dict[str, object]:
  """Structured auth status: {mode, source, endpoint, credential, ok, hint}.

  Azure mode requires BOTH an endpoint (OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT) and
  an api key. `ok` is False (and `hint` populated) when either is missing — surfaces
  the failure at audit time instead of letting it explode at request time.
  """
  enabled = _cfg.load().get("enabled_providers", [])
  in_config = "openai_azure" in enabled or "openai_direct" in enabled
  source = "config" if in_config else "env"

  if "openai_azure" in enabled or (not in_config and is_azure()):
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
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
      + ". Set in env (e.g. OPENAI_BASE_URL=https://<resource>.openai.azure.com) "
      + "or switch to openai_direct via `genimg setup`."
    )
    return {
      "mode": "azure", "source": source,
      "endpoint": endpoint or "-",
      "credential": cred,
      "ok": ok, "hint": hint,
    }
  if "openai_direct" in enabled or (not in_config and os.getenv("OPENAI_API_KEY")):
    ok = bool(os.getenv("OPENAI_API_KEY"))
    return {
      "mode": "direct", "source": source,
      "endpoint": os.getenv("OPENAI_BASE_URL") or "https://api.openai.com",
      "credential": "OPENAI_API_KEY" if ok else "-",
      "ok": ok,
      "hint": "" if ok else "Direct mode needs OPENAI_API_KEY in env.",
    }
  return {
    "mode": "unset", "source": "-", "endpoint": "-", "credential": "-",
    "ok": False,
    "hint": "Run `genimg setup` or set OPENAI_API_KEY (direct) or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY (Azure).",
  }


def auth_mode() -> str:
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
