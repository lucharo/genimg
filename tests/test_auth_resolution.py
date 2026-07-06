from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genimg.auth import google as ag
from genimg.auth import openai as ao

# Env vars that steer auth resolution; cleared per-test so ambient values don't leak in.
_AUTH_ENV = (
  "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT",
  "OPENAI_API_VERSION", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
  "CLAUDE_GCP_CRED", "GOOGLE_CLOUD_PROJECT", "GOOGLE_GENAI_USE_VERTEXAI",
  "ANTHROPIC_VERTEX_PROJECT_ID",
)


class _CleanEnv(unittest.TestCase):
  def setUp(self) -> None:
    self._env = patch.dict(os.environ, {}, clear=False)  # snapshots + restores on stop
    self._env.start()
    self.addCleanup(self._env.stop)
    for k in _AUTH_ENV:
      os.environ.pop(k, None)


class OpenAIResolutionTests(_CleanEnv):
  def test_config_azure_wins(self) -> None:
    with patch.object(ao._cfg, "load", return_value={"enabled_providers": ["openai_azure"]}), \
         patch.object(ao, "_azure", return_value="AZURE") as az:
      self.assertEqual(ao.get_client(), "AZURE")
      az.assert_called_once()

  def test_config_native_bypasses_env_base_url(self) -> None:
    os.environ["OPENAI_BASE_URL"] = "https://x.azure.com/y"
    with patch.object(ao._cfg, "load", return_value={"enabled_providers": ["openai_native"]}), \
         patch.object(ao, "_direct", return_value="DIRECT") as di:
      self.assertEqual(ao.get_client(), "DIRECT")
      di.assert_called_once_with(ignore_base_url=True)

  def test_force_direct(self) -> None:
    with patch.object(ao, "_direct", return_value="DIRECT") as di:
      self.assertEqual(ao.get_client(force="direct"), "DIRECT")
      di.assert_called_once_with(ignore_base_url=True)

  def test_env_fallback_azure(self) -> None:
    os.environ["AZURE_OPENAI_ENDPOINT"] = "https://x.openai.azure.com"
    with patch.object(ao._cfg, "load", return_value={}), \
         patch.object(ao, "_azure", return_value="AZURE") as az:
      self.assertEqual(ao.get_client(), "AZURE")
      az.assert_called_once()


class GoogleResolutionTests(_CleanEnv):
  def test_config_vertex_without_cred_raises(self) -> None:
    with patch.object(ag._cfg, "load", return_value={"enabled_providers": ["google_vertex"]}):
      with self.assertRaises(RuntimeError):
        ag.get_client()

  def test_config_vertex_with_cred(self) -> None:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/x.json"
    with patch.object(ag._cfg, "load", return_value={"enabled_providers": ["google_vertex"]}), \
         patch.object(ag, "_vertex", return_value="VTX") as v:
      self.assertEqual(ag.get_client(), "VTX")
      v.assert_called_once()

  def test_config_direct_with_key(self) -> None:
    os.environ["GEMINI_API_KEY"] = "k"
    with patch.object(ag._cfg, "load", return_value={"enabled_providers": ["google_direct"]}), \
         patch.object(ag, "_direct", return_value="DIR") as d:
      self.assertEqual(ag.get_client(), "DIR")
      d.assert_called_once()

  def test_no_auth_raises(self) -> None:
    with patch.object(ag._cfg, "load", return_value={}):
      with self.assertRaises(RuntimeError):
        ag.get_client()


class ProjectResolutionTests(_CleanEnv):
  def test_precedence(self) -> None:
    self.assertEqual(ag._resolve_project("explicit", {"gcp_project": "cfg"}, use_gcloud=False), "explicit")
    self.assertEqual(ag._resolve_project(None, {"gcp_project": "cfg"}, use_gcloud=False), "cfg")
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
    from unittest.mock import MagicMock
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
