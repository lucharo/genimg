"""config.toml round-trips and profile helpers."""
from __future__ import annotations

import pytest

from genimg import config


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
  monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
  monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.toml")
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


@pytest.mark.parametrize("editor,argv", [
  ("code --wait", ["code", "--wait"]),
  ('"/Applications/My Editor/bin/edit" -w', ["/Applications/My Editor/bin/edit", "-w"]),
  ("", ["vi"]),
])
def test_editor_command_is_split_like_a_shell_would(config_dir, monkeypatch, editor, argv):
  monkeypatch.setenv("EDITOR", editor)
  calls = []
  monkeypatch.setattr("subprocess.run", lambda cmd, **kw: calls.append(cmd))
  config.open_in_editor()
  assert calls == [[*argv, str(config_dir / "config.toml")]]
