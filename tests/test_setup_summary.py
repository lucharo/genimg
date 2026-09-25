"""The setup wizard's closing summary, and the unattended run an agent drives without a terminal."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from genimg import cli, setup
from genimg.auth import codex as auth_codex
from genimg.auth import google as auth_google


def test_profile_line_keeps_the_table_name_rich_would_eat():
  console = Console(record=True, width=120)

  console.print(setup._profile_line("google", {"provider": "google", "auth": "direct", "region": "global"}))

  assert console.export_text().strip() == "[profiles.google] google / direct  (region=global)"


_CRED_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "CLAUDE_GCP_CRED",
              "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "OPENAI_BASE_URL")


@pytest.fixture
def unattended(tmp_path, monkeypatch):
  """CliRunner's stdin is not a TTY. Only a Gemini key is in env; no gcloud, no Codex login,
  and any prompt fails the test."""
  monkeypatch.setattr(setup.config, "CONFIG_PATH", tmp_path / "config.toml")
  for var in _CRED_VARS:
    monkeypatch.delenv(var, raising=False)
  monkeypatch.setenv("GEMINI_API_KEY", "k")
  monkeypatch.setattr(auth_google, "adc_token_present", lambda: False)
  monkeypatch.setattr(auth_codex, "login_status", lambda: (False, "Run `codex login` with ChatGPT."))
  for prompt in ("select", "confirm", "text", "password", "path"):
    monkeypatch.setattr(setup.questionary, prompt, lambda *a, **k: pytest.fail("unattended setup prompted"))
  return tmp_path / "config.toml"


def test_unattended_setup_saves_each_detected_provider_that_validates(unattended):
  with patch.object(auth_google.GoogleDirect, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup", "--model", "gdm:nano-banana-2"])

  assert result.exit_code == 0, result.output
  assert setup.config.load() == {"profiles": {"google": {"provider": "google", "auth": "direct"}},
                                 "default_model": "gdm:nb2"}
  lines = [" ".join(line.split()) for line in result.output.splitlines()]
  assert "Google · Gemini: saved (direct)" in lines
  assert "OpenAI: skipped: no credentials detected (`genimg auth --modes` lists the env vars)" in lines
  assert "Codex subscription: skipped: no credentials detected (Run `codex login` with ChatGPT.)" in lines
  assert "[profiles.google] google / direct" in lines
  assert "default model: gdm:nb2" in lines


def test_unattended_setup_keeps_the_existing_default_without_model(unattended):
  setup.config.save({"default_model": "oai:gpt-image-2"})
  with patch.object(auth_google.GoogleDirect, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup"])

  assert result.exit_code == 0, result.output
  assert setup.config.load()["default_model"] == "oai:gpt-image-2"


def test_unattended_setup_fails_when_no_provider_validates(unattended):
  with patch.object(auth_google.GoogleDirect, "validate", return_value=(False, "401: API key not valid")):
    result = CliRunner().invoke(cli._app, ["setup"])

  assert result.exit_code == 1, result.output
  output = " ".join(result.output.split())
  assert "Google · Gemini: skipped: Direct API (Gemini key) validation failed: 401: API key not valid" in output
  assert "No provider validated; config not changed." in output
  assert not unattended.exists()


def test_setup_rejects_an_unknown_model_before_touching_config(unattended):
  result = CliRunner().invoke(cli._app, ["setup", "--model", "gdm:nope"])

  assert result.exit_code == 1, result.output
  assert "unknown model 'gdm:nope'" in result.output
  assert not unattended.exists()


def test_unattended_setup_does_not_save_a_model_no_profile_covers(unattended):
  with patch.object(auth_google.GoogleDirect, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup", "--model", "oai:gi2"])

  assert result.exit_code == 1, result.output
  assert setup.config.load() == {"profiles": {"google": {"provider": "google", "auth": "direct"}}}
  assert ("default model not saved: oai:gpt-image-2 needs a openai profile, and there is none."
          in " ".join(result.output.split()))


def test_unattended_setup_falls_back_to_the_next_detected_mode(unattended, monkeypatch, tmp_path):
  monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "sa.json"))
  monkeypatch.setattr(auth_google, "_gcloud_project", lambda: "gcloud-active-project")
  with patch.object(auth_google.GoogleVertex, "validate", return_value=(False, "403: permission denied")), \
       patch.object(auth_google.GoogleDirect, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup"])

  assert result.exit_code == 0, result.output
  assert setup.config.load() == {"profiles": {"google": {"provider": "google", "auth": "direct"}}}


def test_unattended_vertex_profile_leaves_the_project_to_runtime_resolution(unattended, monkeypatch, tmp_path):
  monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "sa.json"))
  monkeypatch.setattr(auth_google, "_gcloud_project", lambda: "gcloud-active-project")
  with patch.object(auth_google.GoogleVertex, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup"])

  assert result.exit_code == 0, result.output
  assert setup.config.load() == {"profiles": {"google": {"provider": "google", "auth": "vertex"}}}


def test_unattended_setup_drops_a_logged_out_codex_profile_like_the_wizard(unattended):
  setup.config.save({"profiles": {"codex": {"provider": "codex", "auth": "subscription"}},
                     "default_model": "codex:image"})
  with patch.object(auth_google.GoogleDirect, "validate", return_value=(True, "")):
    result = CliRunner().invoke(cli._app, ["setup"])

  assert result.exit_code == 0, result.output
  assert setup.config.load() == {"profiles": {"google": {"provider": "google", "auth": "direct"}}}
