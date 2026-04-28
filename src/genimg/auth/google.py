"""google-genai client factory. Config wins (`genimg setup`), env is fallback."""
from __future__ import annotations

import os

from google import genai

from .. import config as _cfg

ORG_DEFAULT_PROJECT = "example-gcp-project"


def _vertex(project: str | None, region: str) -> genai.Client:
  cred = os.getenv("CLAUDE_GCP_CRED")
  if cred:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred
  user_cfg = _cfg.load()
  proj = project or user_cfg.get("gcp_project") or os.getenv("ANTHROPIC_VERTEX_PROJECT_ID") \
    or os.getenv("GOOGLE_CLOUD_PROJECT") or ORG_DEFAULT_PROJECT
  loc = user_cfg.get("gcp_region") or region
  return genai.Client(vertexai=True, project=proj, location=loc)


def _direct() -> genai.Client:
  return genai.Client()


def get_client(region: str = "global", project: str | None = None) -> genai.Client:
  """Return a configured genai.Client. Resolution: saved config → env detection."""
  enabled = _cfg.load().get("enabled_providers", [])

  if "google_vertex" in enabled:
    if os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
      return _vertex(project, region)
    raise RuntimeError(
      "config says google_vertex but no CLAUDE_GCP_CRED / GOOGLE_APPLICATION_CREDENTIALS in env. "
      "Set one or re-run `genimg setup`."
    )
  if "google_direct" in enabled:
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
      return _direct()
    raise RuntimeError(
      "config says google_direct but no GEMINI_API_KEY / GOOGLE_API_KEY in env. "
      "Set one or re-run `genimg setup`."
    )

  # No config preference → env auto-detection (legacy behavior)
  if os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS") \
     or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}:
    return _vertex(project, region)
  if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
    return _direct()
  raise RuntimeError(
    "No Google auth detected. Run `genimg setup` or set CLAUDE_GCP_CRED / GEMINI_API_KEY / GOOGLE_API_KEY."
  )


def auth_info() -> dict[str, str]:
  """Structured auth status: {mode, endpoint, credential, source}."""
  enabled = _cfg.load().get("enabled_providers", [])
  source = "config" if ("google_vertex" in enabled or "google_direct" in enabled) else "env"

  if "google_vertex" in enabled or os.getenv("CLAUDE_GCP_CRED"):
    return {
      "mode": "vertex", "source": source,
      "endpoint": _cfg.load().get("gcp_project") or os.getenv("ANTHROPIC_VERTEX_PROJECT_ID") or ORG_DEFAULT_PROJECT,
      "credential": "CLAUDE_GCP_CRED" if os.getenv("CLAUDE_GCP_CRED") else "GOOGLE_APPLICATION_CREDENTIALS",
    }
  if "google_direct" in enabled or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
    cred = "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY") else "GOOGLE_API_KEY"
    return {"mode": "direct", "source": source, "endpoint": "generativelanguage.googleapis.com", "credential": cred}
  if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}:
    return {
      "mode": "vertex", "source": "env",
      "endpoint": os.getenv("GOOGLE_CLOUD_PROJECT") or ORG_DEFAULT_PROJECT,
      "credential": "GOOGLE_APPLICATION_CREDENTIALS",
    }
  return {"mode": "unset", "source": "-", "endpoint": "-", "credential": "-"}


def auth_mode() -> str:
  """One-line summary for inline display."""
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
