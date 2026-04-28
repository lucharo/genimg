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


def _direct() -> OpenAI:
  if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("Direct OpenAI mode requires OPENAI_API_KEY.")
  return OpenAI()


def get_client(*, force: str | None = None) -> OpenAI | AzureOpenAI:
  """Return OpenAI or AzureOpenAI client. Resolution: --auth flag → saved config → env."""
  if force == "azure":
    return _azure()
  if force == "direct":
    return _direct()

  enabled = _cfg.load().get("enabled_providers", [])
  if "openai_azure" in enabled:
    return _azure()
  if "openai_direct" in enabled:
    return _direct()

  # No config preference → env auto-detection
  return _azure() if is_azure() else _direct()


def auth_info() -> dict[str, str]:
  """Structured auth status: {mode, endpoint, credential, source}."""
  enabled = _cfg.load().get("enabled_providers", [])
  in_config = "openai_azure" in enabled or "openai_direct" in enabled
  source = "config" if in_config else "env"

  if "openai_azure" in enabled or (not in_config and is_azure()):
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_BASE_URL") or "-"
    cred = "AZURE_OPENAI_API_KEY" if os.getenv("AZURE_OPENAI_API_KEY") else "OPENAI_API_KEY"
    return {"mode": "azure", "source": source, "endpoint": endpoint, "credential": cred}
  if "openai_direct" in enabled or (not in_config and os.getenv("OPENAI_API_KEY")):
    return {
      "mode": "direct", "source": source,
      "endpoint": os.getenv("OPENAI_BASE_URL") or "https://api.openai.com",
      "credential": "OPENAI_API_KEY",
    }
  return {"mode": "unset", "source": "-", "endpoint": "-", "credential": "-"}


def auth_mode() -> str:
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
