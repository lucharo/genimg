"""google-genai client factory. Config wins (`genimg setup`), env is fallback."""
from __future__ import annotations

import os

from google import genai

from .. import config as _cfg

GSK_DEFAULT_PROJECT = "gsk-rd-oaiml-kgapoc1-dev"


def _vertex(project: str | None, region: str) -> genai.Client:
  cred = os.getenv("CLAUDE_GCP_CRED")
  if cred:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred
  user_cfg = _cfg.load()
  proj = project or user_cfg.get("gcp_project") or os.getenv("ANTHROPIC_VERTEX_PROJECT_ID") \
    or os.getenv("GOOGLE_CLOUD_PROJECT") or GSK_DEFAULT_PROJECT
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


def auth_info() -> dict[str, object]:
  """Structured auth status: {mode, source, endpoint, credential, ok, hint}.

  `ok` is True iff the credentials needed for the resolved mode are actually present
  in env (preflight check, not a live API probe). `hint` is empty when ok, otherwise
  a one-line description of what's missing.
  """
  enabled = _cfg.load().get("enabled_providers", [])
  in_config = "google_vertex" in enabled or "google_direct" in enabled
  source = "config" if in_config else "env"

  if "google_vertex" in enabled or os.getenv("CLAUDE_GCP_CRED"):
    cred_var = (
      "CLAUDE_GCP_CRED" if os.getenv("CLAUDE_GCP_CRED")
      else "GOOGLE_APPLICATION_CREDENTIALS" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
      else "-"
    )
    ok = cred_var != "-"
    return {
      "mode": "vertex", "source": source,
      "endpoint": _cfg.load().get("gcp_project") or os.getenv("ANTHROPIC_VERTEX_PROJECT_ID") or GSK_DEFAULT_PROJECT,
      "credential": cred_var,
      "ok": ok,
      "hint": "" if ok else (
        "Vertex needs CLAUDE_GCP_CRED or GOOGLE_APPLICATION_CREDENTIALS pointing at a "
        "service-account JSON. Set one or switch to google_direct via `genimg setup`."
      ),
    }
  if "google_direct" in enabled or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
    cred = (
      "GEMINI_API_KEY" if os.getenv("GEMINI_API_KEY")
      else "GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY")
      else "-"
    )
    ok = cred != "-"
    return {
      "mode": "direct", "source": source,
      "endpoint": "generativelanguage.googleapis.com",
      "credential": cred,
      "ok": ok,
      "hint": "" if ok else "Direct API needs GOOGLE_API_KEY or GEMINI_API_KEY in env.",
    }
  if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}:
    return {
      "mode": "vertex", "source": "env",
      "endpoint": os.getenv("GOOGLE_CLOUD_PROJECT") or GSK_DEFAULT_PROJECT,
      "credential": "GOOGLE_APPLICATION_CREDENTIALS",
      "ok": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
      "hint": "" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") else (
        "GOOGLE_GENAI_USE_VERTEXAI is set but no credentials file. "
        "Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json."
      ),
    }
  return {
    "mode": "unset", "source": "-", "endpoint": "-", "credential": "-",
    "ok": False,
    "hint": "Run `genimg setup` or set GOOGLE_API_KEY (direct) or CLAUDE_GCP_CRED (Vertex).",
  }


def auth_mode() -> str:
  """One-line summary for inline display."""
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
