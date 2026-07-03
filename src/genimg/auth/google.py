"""google-genai client factory. Config wins (`genimg setup`), env is fallback.

Three modes:
  google_direct      — GEMINI_API_KEY / GOOGLE_API_KEY  → generativelanguage.googleapis.com
  google_vertex      — service-account JSON via CLAUDE_GCP_CRED / GOOGLE_APPLICATION_CREDENTIALS
  google_vertex_adc  — gcloud user creds via `gcloud auth application-default login`
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from google import genai

from .. import config as _cfg


def _project_from_sa_json() -> str | None:
  """project_id embedded in the service-account JSON (CLAUDE_GCP_CRED /
  GOOGLE_APPLICATION_CREDENTIALS), if present and parseable. Reading the id does
  not authenticate as the SA."""
  path = os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
  if not path:
    return None
  try:
    pid = json.loads(Path(path).read_text()).get("project_id")
  except (OSError, json.JSONDecodeError, AttributeError):
    return None
  return pid if isinstance(pid, str) and pid else None


def _gcloud_project() -> str | None:
  """gcloud's active project, if the CLI is installed and configured."""
  if not shutil.which("gcloud"):
    return None
  try:
    r = subprocess.run(
      ["gcloud", "config", "get-value", "project"],
      capture_output=True, text=True, timeout=5,
    )
    if r.returncode != 0:
      return None
    proj = r.stdout.strip()
    # gcloud prints "(unset)" (and sometimes empty) when no project is configured.
    return proj if proj and proj != "(unset)" else None
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return None


def _resolve_project(project: str | None, user_cfg: dict, *, use_gcloud: bool) -> str | None:
  """--project → config → GOOGLE_CLOUD_PROJECT → SA-JSON project_id → (gcloud, ADC only).

  No hardcoded fallback: a wrong project silently routes requests to the wrong place.
  `use_gcloud` gates the gcloud subprocess so it stays off the hot path for non-ADC modes.
  """
  return (
    project
    or user_cfg.get("gcp_project")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or _project_from_sa_json()
    or (_gcloud_project() if use_gcloud else None)
  )


def _require_project(project: str | None, user_cfg: dict, *, use_gcloud: bool) -> str:
  proj = _resolve_project(project, user_cfg, use_gcloud=use_gcloud)
  if not proj:
    raise RuntimeError(
      "No GCP project for Vertex. Set one via `genimg setup`, --project, config.gcp_project, "
      "or GOOGLE_CLOUD_PROJECT (a service-account JSON's project_id and gcloud's active "
      "project are used automatically when available)."
    )
  return proj


def _vertex(project: str | None, region: str) -> genai.Client:
  cred = os.getenv("CLAUDE_GCP_CRED")
  if cred:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred
  user_cfg = _cfg.load()
  proj = _require_project(project, user_cfg, use_gcloud=False)
  loc = user_cfg.get("gcp_region") or region
  return genai.Client(vertexai=True, project=proj, location=loc)


def _vertex_adc(project: str | None, region: str) -> genai.Client:
  """Force Vertex auth via gcloud user ADC.

  The SDK's google.auth.default() resolution picks up GOOGLE_APPLICATION_CREDENTIALS
  *first*, then falls back to gcloud ADC. If a service-account env var is set we'd
  silently auth as the SA — defeating the user's explicit `google_vertex_adc` choice.
  Hide those vars during client construction so ADC actually wins.
  """
  user_cfg = _cfg.load()
  proj = _require_project(project, user_cfg, use_gcloud=True)
  loc = user_cfg.get("gcp_region") or region
  hidden = {k: os.environ.pop(k, None) for k in ("GOOGLE_APPLICATION_CREDENTIALS", "CLAUDE_GCP_CRED")}
  try:
    return genai.Client(vertexai=True, project=proj, location=loc)
  finally:
    for k, v in hidden.items():
      if v is not None:
        os.environ[k] = v


def _direct() -> genai.Client:
  return genai.Client()


def adc_token_present() -> bool:
  """True if `gcloud auth application-default print-access-token` returns a token."""
  if not shutil.which("gcloud"):
    return False
  try:
    r = subprocess.run(
      ["gcloud", "auth", "application-default", "print-access-token"],
      capture_output=True, text=True, timeout=5,
    )
    return r.returncode == 0 and bool(r.stdout.strip())
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return False


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
  if "google_vertex_adc" in enabled:
    if adc_token_present():
      return _vertex_adc(project, region)
    raise RuntimeError(
      "config says google_vertex_adc but no ADC token. "
      "Run `gcloud auth application-default login` and try again."
    )
  if "google_direct" in enabled:
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
      return _direct()
    raise RuntimeError(
      "config says google_direct but no GEMINI_API_KEY / GOOGLE_API_KEY in env. "
      "Set one or re-run `genimg setup`."
    )

  if os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS") \
     or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}:
    return _vertex(project, region)
  if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
    return _direct()
  raise RuntimeError(
    "No Google auth detected. Run `genimg setup` or set CLAUDE_GCP_CRED / GEMINI_API_KEY / GOOGLE_API_KEY."
  )


def validate(mode: str, *, project: str | None = None, region: str = "us-central1") -> tuple[bool, str]:
  """Live preflight via `client.models.list()` — free, no image generated.

  Returns (ok, error_msg). `mode` ∈ {google_direct, google_vertex, google_vertex_adc}.
  """
  try:
    if mode == "google_direct":
      if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        return False, "GEMINI_API_KEY / GOOGLE_API_KEY not in env"
      client = _direct()
    elif mode == "google_vertex":
      if not (os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
        return False, "CLAUDE_GCP_CRED / GOOGLE_APPLICATION_CREDENTIALS not in env"
      client = _vertex(project, region)
    elif mode == "google_vertex_adc":
      if not adc_token_present():
        return False, "no gcloud ADC token (run `gcloud auth application-default login`)"
      client = _vertex_adc(project, region)
    else:
      return False, f"unknown mode: {mode}"
    next(iter(client.models.list()), None)
    return True, ""
  except Exception as e:
    return False, f"{type(e).__name__}: {str(e)[:300]}"


def auth_info() -> dict[str, object]:
  """Structured auth status: {mode, source, endpoint, credential, ok, hint}.

  `ok` is True iff the credentials needed for the resolved mode are present in env
  (preflight, not a live API probe). `hint` is empty when ok, otherwise a one-line
  description of what's missing.
  """
  user_cfg = _cfg.load()
  enabled = user_cfg.get("enabled_providers", [])
  in_config = any(m in enabled for m in ("google_vertex", "google_vertex_adc", "google_direct"))
  source = "config" if in_config else "env"
  # Display-only: use_gcloud=False keeps the gcloud subprocess off the generate hot path
  # (auth_info runs on every generate for the mode banner).
  project = _resolve_project(None, user_cfg, use_gcloud=False) or "-"

  if "google_vertex_adc" in enabled:
    ok = adc_token_present()
    return {
      "mode": "vertex_adc", "source": source,
      "endpoint": project,
      "credential": "gcloud ADC",
      "ok": ok,
      "hint": "" if ok else (
        "No active ADC token. Run `gcloud auth application-default login` "
        "(or switch to google_vertex / google_direct via `genimg setup`)."
      ),
    }
  if "google_vertex" in enabled or os.getenv("CLAUDE_GCP_CRED"):
    cred_var = (
      "CLAUDE_GCP_CRED" if os.getenv("CLAUDE_GCP_CRED")
      else "GOOGLE_APPLICATION_CREDENTIALS" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
      else "-"
    )
    ok = cred_var != "-"
    return {
      "mode": "vertex", "source": source,
      "endpoint": project,
      "credential": cred_var,
      "ok": ok,
      "hint": "" if ok else (
        "Vertex needs CLAUDE_GCP_CRED or GOOGLE_APPLICATION_CREDENTIALS pointing at a "
        "service-account JSON. Set one or switch via `genimg setup`."
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
      "endpoint": project,
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
