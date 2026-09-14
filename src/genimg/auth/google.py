"""Google auth profiles for google-genai.

  direct      — GEMINI_API_KEY / GOOGLE_API_KEY  → generativelanguage.googleapis.com
  vertex      — service-account JSON via GOOGLE_APPLICATION_CREDENTIALS (or CLAUDE_GCP_CRED)
  vertex_adc  — gcloud user creds via `gcloud auth application-default login`

Profile settings: `project` (Vertex GCP project), `region` (Vertex location).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from google import genai

from .base import AuthInfo, AuthProfile, SecretSpec, SettingSpec

_SA_VARS = ("GOOGLE_APPLICATION_CREDENTIALS", "CLAUDE_GCP_CRED")
_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
DEFAULT_REGION = "global"


# ── project resolution ──

def _sa_path() -> str | None:
  return os.getenv("CLAUDE_GCP_CRED") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


def _project_from_sa_json() -> str | None:
  """project_id embedded in the service-account JSON, if present and parseable.
  Reading the id does not authenticate as the SA."""
  path = _sa_path()
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
    r = subprocess.run(["gcloud", "config", "get-value", "project"],
                       capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
      return None
    proj = r.stdout.strip()
    return proj if proj and proj != "(unset)" else None
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return None


def _resolve_project(project: str | None, settings: dict[str, Any], *, use_gcloud: bool) -> str | None:
  """--project → profile.project → GOOGLE_CLOUD_PROJECT → SA-JSON project_id → (gcloud, ADC only).

  No hardcoded fallback: a wrong project silently routes requests to the wrong place.
  `use_gcloud` gates the gcloud subprocess so it stays off the hot path for non-ADC modes.
  """
  return (
    project
    or settings.get("project")
    or os.getenv("GOOGLE_CLOUD_PROJECT")
    or _project_from_sa_json()
    or (_gcloud_project() if use_gcloud else None)
  )


def _require_project(project: str | None, settings: dict[str, Any], *, use_gcloud: bool) -> str:
  proj = _resolve_project(project, settings, use_gcloud=use_gcloud)
  if not proj:
    raise RuntimeError(
      "No GCP project for Vertex. Set one via `genimg setup`, --project, the profile's "
      "`project` setting, or GOOGLE_CLOUD_PROJECT (a service-account JSON's project_id and "
      "gcloud's active project are used automatically when available)."
    )
  return proj


def adc_token_present() -> bool:
  """True if `gcloud auth application-default print-access-token` returns a token."""
  if not shutil.which("gcloud"):
    return False
  try:
    r = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                       capture_output=True, text=True, timeout=5)
    return r.returncode == 0 and bool(r.stdout.strip())
  except (subprocess.TimeoutExpired, FileNotFoundError):
    return False


def _preflight(client: genai.Client) -> tuple[bool, str]:
  try:
    next(iter(client.models.list()), None)
    return True, ""
  except Exception as e:
    return False, f"{type(e).__name__}: {str(e)[:300]}"


# ── profiles ──

class GoogleDirect(AuthProfile):
  provider = "google"
  mode = "direct"
  label = "Direct API (Gemini key)"
  env_vars = _KEY_VARS
  secret = SecretSpec("GEMINI_API_KEY", "Gemini API key", "https://aistudio.google.com/apikey")

  def detect(self) -> bool:
    return bool(self.present_env_var())

  def client(self, **kw: Any) -> genai.Client:
    if not self.detect():
      raise RuntimeError(f"{self.source}: google direct mode needs GEMINI_API_KEY or GOOGLE_API_KEY in env.")
    return genai.Client()

  def validate(self) -> tuple[bool, str]:
    if not self.detect():
      return False, "GEMINI_API_KEY / GOOGLE_API_KEY not in env"
    return _preflight(self.client())

  def info(self) -> AuthInfo:
    cred = self.present_env_var()
    return AuthInfo(mode=self.mode, source=self.source, endpoint="generativelanguage.googleapis.com",
                    credential=cred or "-", ok=bool(cred), profile=self.name,
                    hint="" if cred else "Direct API needs GEMINI_API_KEY or GOOGLE_API_KEY in env.")


class _VertexBase(AuthProfile):
  provider = "google"
  settings_spec = (
    SettingSpec("project", "GCP project ID for Vertex (leave empty for SDK default):",
                detect=lambda: _gcloud_project()),
  )

  def region(self, override: str | None = None) -> str:
    return override or self.settings.get("region") or DEFAULT_REGION

  def _client(self, project: str | None, region: str | None, *, use_gcloud: bool) -> genai.Client:
    proj = _require_project(project, self.settings, use_gcloud=use_gcloud)
    return genai.Client(vertexai=True, project=proj, location=self.region(region))

  def _project_label(self) -> str:
    return _resolve_project(None, self.settings, use_gcloud=False) or "-"


class GoogleVertex(_VertexBase):
  mode = "vertex"
  label = "Vertex (service account JSON)"
  env_vars = _SA_VARS
  secret = SecretSpec("GOOGLE_APPLICATION_CREDENTIALS", "service-account JSON",
                      "https://console.cloud.google.com/iam-admin/serviceaccounts", kind="path")

  def detect(self) -> bool:
    return bool(_sa_path())

  def client(self, *, project: str | None = None, region: str | None = None, **kw: Any) -> genai.Client:
    cred = os.getenv("CLAUDE_GCP_CRED")
    if cred:
      os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred
    if not self.detect():
      raise RuntimeError(
        f"{self.source}: google vertex mode needs GOOGLE_APPLICATION_CREDENTIALS (or CLAUDE_GCP_CRED) "
        "pointing at a service-account JSON. Set one or re-run `genimg setup`."
      )
    return self._client(project, region, use_gcloud=False)

  def validate(self) -> tuple[bool, str]:
    if not self.detect():
      return False, "GOOGLE_APPLICATION_CREDENTIALS / CLAUDE_GCP_CRED not in env"
    try:
      return _preflight(self.client())
    except RuntimeError as e:
      return False, str(e)

  def info(self) -> AuthInfo:
    cred = self.present_env_var()
    return AuthInfo(mode=self.mode, source=self.source, endpoint=self._project_label(),
                    credential=cred or "-", ok=bool(cred), profile=self.name,
                    hint="" if cred else ("Vertex needs GOOGLE_APPLICATION_CREDENTIALS (or CLAUDE_GCP_CRED) "
                                          "pointing at a service-account JSON. Set one or switch via `genimg setup`."))


class GoogleVertexADC(_VertexBase):
  mode = "vertex_adc"
  label = "Vertex (gcloud user creds, ADC)"
  env_vars = ()

  def detect(self) -> bool:
    return adc_token_present()

  def detail(self) -> str:
    return "gcloud token active" if self.detect() else "run `gcloud auth application-default login`"

  def client(self, *, project: str | None = None, region: str | None = None, **kw: Any) -> genai.Client:
    """The SDK's google.auth.default() picks GOOGLE_APPLICATION_CREDENTIALS first and only then
    gcloud ADC. Hide the SA vars during construction so the explicit ADC choice wins."""
    if not self.detect():
      raise RuntimeError(f"{self.source}: no gcloud ADC token. Run `gcloud auth application-default login`.")
    hidden = {k: os.environ.pop(k, None) for k in _SA_VARS}
    try:
      return self._client(project, region, use_gcloud=True)
    finally:
      for k, v in hidden.items():
        if v is not None:
          os.environ[k] = v

  def validate(self) -> tuple[bool, str]:
    if not self.detect():
      return False, "no gcloud ADC token (run `gcloud auth application-default login`)"
    try:
      return _preflight(self.client())
    except RuntimeError as e:
      return False, str(e)

  def info(self) -> AuthInfo:
    ok = self.detect()
    return AuthInfo(mode=self.mode, source=self.source, endpoint=self._project_label(),
                    credential="gcloud ADC" if ok else "-", ok=ok, profile=self.name,
                    hint="" if ok else ("No active ADC token. Run `gcloud auth application-default login` "
                                        "(or switch to vertex / direct via `genimg setup`)."))


# Detection order for env auto-resolution: an explicit SA file wins over an API key, ADC last
# (it needs a gcloud subprocess). GOOGLE_GENAI_USE_VERTEXAI=1 forces the vertex branch upstream.
MODES: tuple[type[AuthProfile], ...] = (GoogleVertex, GoogleDirect, GoogleVertexADC)


# ── compatibility wrappers (older call sites and tests) ──

def get_client(region: str = DEFAULT_REGION, project: str | None = None, *,
               profile: AuthProfile | None = None) -> genai.Client:
  from .resolve import resolve
  p = profile or resolve("google")
  return p.client(project=project, region=region)


def auth_info() -> dict[str, object]:
  from .resolve import info
  return info("google").as_dict()


def auth_mode() -> str:
  i = auth_info()
  return f"{i['mode']} ({i['credential']})" if i["mode"] != "unset" else "unset"
