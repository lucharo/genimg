"""OpenAI auth profiles.

  native — OPENAI_API_KEY → api.openai.com (an OPENAI_BASE_URL proxy is honoured only when
           the profile came from env auto-detection; a configured native profile pins
           api.openai.com so a stray proxy URL cannot hijack it)
  azure  — AZURE_OPENAI_API_KEY (or OPENAI_API_KEY) + resource endpoint

Profile settings: `endpoint` (Azure resource URL), `api_version` (Azure api-version).
"""
from __future__ import annotations

import os
from typing import Any

from openai import AzureOpenAI, OpenAI

from .base import AuthInfo, AuthProfile, SecretSpec, SettingSpec

DEFAULT_AZURE_API_VERSION = "2025-04-01-preview"
NATIVE_BASE_URL = "https://api.openai.com/v1"


def _env_azure_endpoint() -> str | None:
  base = os.getenv("OPENAI_BASE_URL", "")
  if os.getenv("AZURE_OPENAI_ENDPOINT"):
    return os.getenv("AZURE_OPENAI_ENDPOINT")
  return base if "azure.com" in base.lower() else None


def is_azure() -> bool:
  return _env_azure_endpoint() is not None


def _preflight(client: OpenAI | AzureOpenAI) -> tuple[bool, str]:
  try:
    next(iter(client.models.list()), None)
    return True, ""
  except Exception as e:
    return False, f"{type(e).__name__}: {str(e)[:300]}"


class OpenAINative(AuthProfile):
  provider = "openai"
  mode = "native"
  label = "OpenAI native (api.openai.com)"
  env_vars = ("OPENAI_API_KEY",)
  secret = SecretSpec("OPENAI_API_KEY", "OpenAI API key", "https://platform.openai.com/api-keys")

  def detect(self) -> bool:
    # A key plus an Azure-looking base URL is an Azure setup, not a native one.
    return bool(os.getenv("OPENAI_API_KEY")) and not is_azure()

  def base_url(self) -> str:
    if self.source == "env":
      return os.getenv("OPENAI_BASE_URL") or NATIVE_BASE_URL  # LiteLLM / OpenRouter proxies
    return NATIVE_BASE_URL

  def client(self, **kw: Any) -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
      raise RuntimeError(f"{self.source}: openai native mode needs OPENAI_API_KEY in env.")
    return OpenAI(api_key=api_key, base_url=self.base_url())

  def validate(self) -> tuple[bool, str]:
    if not os.getenv("OPENAI_API_KEY"):
      return False, "OPENAI_API_KEY not in env"
    return _preflight(self.client())

  def info(self) -> AuthInfo:
    ok = bool(os.getenv("OPENAI_API_KEY"))
    return AuthInfo(mode=self.mode, source=self.source, endpoint=self.base_url().removesuffix("/v1"),
                    credential="OPENAI_API_KEY" if ok else "-", ok=ok, profile=self.name,
                    hint="" if ok else "Native mode needs OPENAI_API_KEY in env.")


class OpenAIAzure(AuthProfile):
  provider = "openai"
  mode = "azure"
  label = "OpenAI via Azure"
  env_vars = ("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY")
  secret = SecretSpec("AZURE_OPENAI_API_KEY", "Azure OpenAI API key",
                      "https://portal.azure.com/#create/Microsoft.CognitiveServicesOpenAI")
  settings_spec = (
    SettingSpec("endpoint", "Azure resource endpoint URL (https://<resource>.openai.azure.com):",
                required=True, detect=_env_azure_endpoint),
  )

  def endpoint(self) -> str | None:
    return self.settings.get("endpoint") or _env_azure_endpoint()

  def api_key_var(self) -> str | None:
    return self.present_env_var()

  def detect(self) -> bool:
    return bool(self.api_key_var()) and bool(self.endpoint())

  def client(self, **kw: Any) -> AzureOpenAI:
    endpoint = self.endpoint()
    if not endpoint:
      raise RuntimeError(
        f"{self.source}: azure mode needs an endpoint. Set the profile's `endpoint`, "
        "AZURE_OPENAI_ENDPOINT or OPENAI_BASE_URL, or run `genimg setup`."
      )
    var = self.api_key_var()
    if not var:
      raise RuntimeError(f"{self.source}: azure mode needs AZURE_OPENAI_API_KEY (or OPENAI_API_KEY).")
    api_version = self.settings.get("api_version") or os.getenv("OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
    return AzureOpenAI(api_key=os.getenv(var), azure_endpoint=endpoint, api_version=api_version)

  def validate(self) -> tuple[bool, str]:
    if not self.endpoint():
      return False, "no endpoint (profile `endpoint`, AZURE_OPENAI_ENDPOINT or OPENAI_BASE_URL)"
    if not self.api_key_var():
      return False, "no api key (AZURE_OPENAI_API_KEY / OPENAI_API_KEY)"
    return _preflight(self.client())

  def detail(self) -> str:
    var, endpoint = self.api_key_var(), self.endpoint()
    from .base import _mask
    if var and endpoint:
      return f"{var}={_mask(os.getenv(var))}, endpoint {_host(endpoint)}"
    if var:
      return f"key {var}={_mask(os.getenv(var))} OK, endpoint missing"
    if endpoint:
      return f"endpoint {_host(endpoint)} OK, key missing"
    return "needs api key + resource endpoint"

  def info(self) -> AuthInfo:
    endpoint, var = self.endpoint(), self.api_key_var()
    missing = []
    if not endpoint:
      missing.append("endpoint (profile `endpoint`, OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT)")
    if not var:
      missing.append("api key (AZURE_OPENAI_API_KEY or OPENAI_API_KEY)")
    ok = not missing
    return AuthInfo(mode=self.mode, source=self.source, endpoint=endpoint or "-",
                    credential=var or "-", ok=ok, profile=self.name,
                    hint="" if ok else "Azure mode needs " + " and ".join(missing) + ". Run `genimg setup` to fix, or set in env.")


def _host(url: str | None) -> str:
  if not url:
    return ""
  from urllib.parse import urlparse
  return urlparse(url).netloc or url


# Azure first: a key plus an Azure endpoint in env is an Azure setup.
MODES: tuple[type[AuthProfile], ...] = (OpenAIAzure, OpenAINative)


# ── compatibility wrappers ──

def get_client(*, force: str | None = None, profile: AuthProfile | None = None) -> OpenAI | AzureOpenAI:
  """--auth flag → configured profile → env. `force` accepts azure | direct (alias of native)."""
  from .resolve import resolve
  if profile is None:
    profile = resolve("openai", force_mode={"direct": "native"}.get(force, force))
  return profile.client()

