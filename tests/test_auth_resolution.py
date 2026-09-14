"""Auth profile resolution: --profile → forced mode → config profile → env auto-detect."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from genimg import config
from genimg.auth import google as ag
from genimg.auth import openai as ao
from genimg.auth import resolve

# Env vars that steer auth resolution; cleared per-test so ambient values don't leak in.
_AUTH_ENV = (
  "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT",
  "OPENAI_API_VERSION", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
  "CLAUDE_GCP_CRED", "GOOGLE_CLOUD_PROJECT", "GOOGLE_GENAI_USE_VERTEXAI",
)


class _CleanEnv(unittest.TestCase):
  def setUp(self) -> None:
    self._env = patch.dict(os.environ, {}, clear=False)  # snapshots + restores on stop
    self._env.start()
    self.addCleanup(self._env.stop)
    for k in _AUTH_ENV:
      os.environ.pop(k, None)


def _cfg(**profiles) -> dict:
  return {"profiles": {name: table for name, table in profiles.items()}}


class OpenAIResolutionTests(_CleanEnv):
  def test_config_azure_profile_wins_over_env_key(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"
    cfg = _cfg(work={"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com"})
    p = resolve.resolve("openai", cfg=cfg)
    self.assertIsInstance(p, ao.OpenAIAzure)
    self.assertEqual((p.name, p.source, p.endpoint()), ("work", "profile:work", "https://x.openai.azure.com"))

  def test_config_native_profile_pins_api_openai_com(self) -> None:
    os.environ["OPENAI_BASE_URL"] = "https://proxy.example/v1"
    p = resolve.resolve("openai", cfg=_cfg(oai={"provider": "openai", "auth": "native"}))
    self.assertIsInstance(p, ao.OpenAINative)
    self.assertEqual(p.base_url(), ao.NATIVE_BASE_URL)

  def test_env_native_honours_proxy_base_url(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"
    os.environ["OPENAI_BASE_URL"] = "https://proxy.example/v1"
    p = resolve.resolve("openai", cfg={})
    self.assertIsInstance(p, ao.OpenAINative)
    self.assertEqual((p.source, p.base_url()), ("env", "https://proxy.example/v1"))

  def test_env_fallback_azure(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"
    os.environ["AZURE_OPENAI_ENDPOINT"] = "https://x.openai.azure.com"
    p = resolve.resolve("openai", cfg={})
    self.assertIsInstance(p, ao.OpenAIAzure)
    self.assertEqual(p.source, "env")

  def test_forced_mode_reuses_configured_settings(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"
    cfg = _cfg(az={"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com"},
               oai={"provider": "openai", "auth": "native"})
    p = resolve.resolve("openai", force_mode="azure", cfg=cfg)
    self.assertEqual((p.mode, p.source, p.settings), ("azure", "flag", {"endpoint": "https://x.openai.azure.com"}))
    self.assertEqual(resolve.resolve("openai", force_mode="native", cfg=cfg).source, "flag")

  def test_named_profile_must_match_provider(self) -> None:
    cfg = _cfg(g={"provider": "google", "auth": "direct"})
    with self.assertRaisesRegex(RuntimeError, "is for provider 'google'"):
      resolve.resolve("openai", profile_name="g", cfg=cfg)
    with self.assertRaisesRegex(RuntimeError, "no profile 'nope'"):
      resolve.resolve("openai", profile_name="nope", cfg=cfg)

  def test_unknown_mode_in_profile_is_an_error_not_a_fallback(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"  # env would work; a broken profile must not fall through to it
    cfg = _cfg(bad={"provider": "openai", "auth": "magic"})
    with self.assertRaisesRegex(RuntimeError, "unknown auth mode 'magic'.*genimg setup"):
      resolve.resolve("openai", cfg=cfg)
    with self.assertRaisesRegex(RuntimeError, "unknown auth mode 'magic'"):
      resolve.resolve("openai", profile_name="bad", cfg=cfg)
    info = resolve.info("openai", cfg=cfg)  # never raises
    self.assertEqual((info.mode, info.ok), ("unset", False))
    self.assertIn("magic", info.hint)

  def test_profile_flag_wins_over_auth_flag(self) -> None:
    cfg = _cfg(az={"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com"})
    p = resolve.resolve("openai", profile_name="az", force_mode="native", cfg=cfg)
    self.assertEqual((p.mode, p.source), ("azure", "profile:az"))

  def test_codex_without_login_reports_its_own_hint(self) -> None:
    with patch("genimg.auth.codex.login_status", return_value=(False, "Run `codex login` with ChatGPT")):
      with self.assertRaisesRegex(RuntimeError, "codex login"):
        resolve.resolve("codex", cfg={})

  def test_no_auth_raises_with_env_hint(self) -> None:
    with self.assertRaisesRegex(RuntimeError, "AZURE_OPENAI_API_KEY / OPENAI_API_KEY"):
      resolve.resolve("openai", cfg={})

  def test_get_client_force_direct_alias(self) -> None:
    os.environ["OPENAI_API_KEY"] = "k"
    with patch.object(config, "load", return_value={}):
      client = ao.get_client(force="direct")
    self.assertEqual(str(client.base_url), ao.NATIVE_BASE_URL + "/")


class GoogleResolutionTests(_CleanEnv):
  def test_config_vertex_without_cred_raises(self) -> None:
    p = resolve.resolve("google", cfg=_cfg(g={"provider": "google", "auth": "vertex"}))
    with self.assertRaisesRegex(RuntimeError, "GOOGLE_APPLICATION_CREDENTIALS"):
      p.client()

  def test_config_vertex_with_cred(self) -> None:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/x.json"
    p = resolve.resolve("google", cfg=_cfg(g={"provider": "google", "auth": "vertex", "project": "cfg-proj", "region": "eu"}))
    self.assertIsInstance(p, ag.GoogleVertex)
    with patch.object(ag.genai, "Client", return_value="VTX") as client:
      self.assertEqual(p.client(), "VTX")
    client.assert_called_once_with(vertexai=True, project="cfg-proj", location="eu")

  def test_config_direct_with_key(self) -> None:
    os.environ["GEMINI_API_KEY"] = "k"
    p = resolve.resolve("google", cfg=_cfg(g={"provider": "google", "auth": "direct"}))
    self.assertIsInstance(p, ag.GoogleDirect)
    self.assertEqual(p.info().credential, "GEMINI_API_KEY")

  def test_env_detection_prefers_service_account_over_key(self) -> None:
    os.environ["GEMINI_API_KEY"] = "k"
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/x.json"
    self.assertIsInstance(resolve.resolve("google", cfg={}), ag.GoogleVertex)
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS")
    self.assertIsInstance(resolve.resolve("google", cfg={}), ag.GoogleDirect)

  def test_no_auth_raises(self) -> None:
    with patch.object(ag, "adc_token_present", return_value=False):
      with self.assertRaisesRegex(RuntimeError, "No google auth detected"):
        resolve.resolve("google", cfg={})

  def test_adc_hides_service_account_vars_during_client_build(self) -> None:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/sa.json"
    seen: dict[str, str | None] = {}

    def fake_client(**kw):
      seen["sa"] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
      return "ADC"

    p = ag.GoogleVertexADC({"project": "p"})
    with patch.object(ag, "adc_token_present", return_value=True), patch.object(ag.genai, "Client", side_effect=fake_client):
      self.assertEqual(p.client(), "ADC")
    self.assertEqual(seen, {"sa": None})
    self.assertEqual(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], "/sa.json")


class InfoTests(_CleanEnv):
  def test_info_never_raises(self) -> None:
    with patch.object(ag, "adc_token_present", return_value=False):
      info = resolve.info("google", cfg={})
    self.assertEqual((info.mode, info.ok), ("unset", False))
    self.assertIn("genimg setup", info.hint)

  def test_all_info_covers_every_provider(self) -> None:
    from genimg.providers import names
    with patch.object(ag, "adc_token_present", return_value=False), \
         patch("genimg.auth.codex.login_status", return_value=(False, "log in")):
      infos = resolve.all_info(cfg={})
    self.assertEqual(sorted(infos), sorted(names()))


class ProjectResolutionTests(_CleanEnv):
  def test_precedence(self) -> None:
    self.assertEqual(ag._resolve_project("explicit", {"project": "cfg"}, use_gcloud=False), "explicit")
    self.assertEqual(ag._resolve_project(None, {"project": "cfg"}, use_gcloud=False), "cfg")
    os.environ["GOOGLE_CLOUD_PROJECT"] = "envproj"
    self.assertEqual(ag._resolve_project(None, {}, use_gcloud=False), "envproj")

  def test_require_raises_when_absent(self) -> None:
    with self.assertRaises(RuntimeError):
      ag._require_project(None, {}, use_gcloud=False)

  def test_project_from_sa_json(self) -> None:
    p = Path(tempfile.mkdtemp()) / "sa.json"
    p.write_text(json.dumps({"type": "service_account", "project_id": "from-json"}))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p)
    self.assertEqual(ag._project_from_sa_json(), "from-json")

  def test_project_from_sa_json_missing_file(self) -> None:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/does/not/exist.json"
    self.assertIsNone(ag._project_from_sa_json())

  def test_gcloud_project_rejects_unset_and_failure(self) -> None:
    with patch.object(ag.shutil, "which", return_value="/usr/bin/gcloud"):
      cases = [
        (0, "(unset)\n", None),   # gcloud's no-project sentinel
        (0, "\n", None),          # empty
        (1, "my-proj\n", None),   # command failed
        (0, "my-proj\n", "my-proj"),
      ]
      for rc, out, expected in cases:
        with patch.object(ag.subprocess, "run", return_value=MagicMock(returncode=rc, stdout=out)):
          self.assertEqual(ag._gcloud_project(), expected)


if __name__ == "__main__":
  unittest.main()
