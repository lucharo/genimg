"""config.toml round-trips, profile helpers, and the one-shot config.json migration."""
from __future__ import annotations

import json

import pytest

from genimg import config


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
  monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
  monkeypatch.setattr(config, "LEGACY_JSON_PATH", tmp_path / "config.json")
  return tmp_path


def test_save_and_load_round_trip_profiles(config_dir):
  data = {"default_model": "gdm:nb2",
          "profiles": {"work": {"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com"}}}
  config.save(data)
  assert config.load() == data
  assert config.profiles_for("openai") == data["profiles"]
  assert config.profiles_for("google") == {}
  assert 'endpoint = "https://x.openai.azure.com"' in config.dumps(data)


def test_set_and_remove_profile(config_dir):
  config.set_profile("g", {"provider": "google", "auth": "direct"})
  config.set_profile("o", {"provider": "openai", "auth": "direct"})
  assert sorted(config.profiles()) == ["g", "o"]
  assert config.remove_profile("g") is True
  assert config.remove_profile("g") is False
  assert config.load() == {"profiles": {"o": {"provider": "openai", "auth": "direct"}}}
  config.remove_profile("o")
  assert config.load() == {}


def test_legacy_json_is_migrated_once_and_renamed(config_dir):
  legacy = {
    "enabled_providers": ["google_vertex_adc", "openai_azure", "codex"],
    "default_model": "gdm:nb2", "default_quality": "high",
    "gcp_project": "proj", "gcp_region": "europe-west1",
    "openai_base_url": "https://x.openai.azure.com", "azure_api_version": "2025-04-01-preview",
  }
  config.LEGACY_JSON_PATH.write_text(json.dumps(legacy))

  loaded = config.load()

  assert loaded == {
    "default_model": "gdm:nb2", "default_quality": "high",
    "profiles": {
      "google": {"provider": "google", "auth": "vertex_adc", "project": "proj", "region": "europe-west1"},
      "openai": {"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com",
                 "api_version": "2025-04-01-preview"},
      "codex": {"provider": "codex", "auth": "subscription"},
    },
  }
  assert config.CONFIG_PATH.exists()
  assert not config.LEGACY_JSON_PATH.exists()
  assert (config_dir / "config.json.migrated").exists()
  assert config.load() == loaded  # second load reads the TOML, not the migrated JSON


@pytest.mark.parametrize("entry,expected", [
  ("openai_direct", {"provider": "openai", "auth": "direct"}),
  ("google_direct", {"provider": "google", "auth": "direct"}),
])
def test_migrate_legacy_maps_every_known_mode(entry, expected):
  assert config.migrate_legacy({"enabled_providers": [entry], "gcp_project": "ignored-for-direct"}) == {
    "profiles": {expected["provider"]: expected}}


def test_migrate_legacy_skips_unknown_entries_and_missing_settings():
  assert config.migrate_legacy({"enabled_providers": ["mystery"], "default_aspect_ratio": "16:9"}) == {
    "default_aspect_ratio": "16:9"}


def test_unparseable_toml_is_an_error_and_is_never_overwritten(config_dir):
  config.CONFIG_PATH.write_text("this is = not = toml")
  with pytest.raises(config.ConfigError, match="not valid TOML"):
    config.load()
  with pytest.raises(config.ConfigError):
    config.save({"default_model": "gdm:nb2"})
  assert config.CONFIG_PATH.read_text() == "this is = not = toml"
  assert not config.CONFIG_PATH.with_name("config.toml.tmp").exists()


def test_save_is_atomic_and_leaves_no_temp_file(config_dir):
  config.save({"default_model": "gdm:nb2"})
  assert sorted(p.name for p in config_dir.iterdir()) == ["config.toml"]


def test_migrate_legacy_keeps_two_modes_for_one_provider():
  migrated = config.migrate_legacy({"enabled_providers": ["google_direct", "google_vertex"], "gcp_project": "p"})
  assert migrated == {"profiles": {
    "google_direct": {"provider": "google", "auth": "direct"},
    "google_vertex": {"provider": "google", "auth": "vertex", "project": "p"},
  }}
