from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from genimg import cli, metadata
from genimg.auth.base import AuthInfo
from genimg.interfaces import GenerateResult


class ModelDefaultTests(unittest.TestCase):
  def test_retired_default_explains_recovery_without_changing_config(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      config_path = Path(td) / "config.toml"
      saved = 'default_model = "gdm:imagen4"\ndefault_quality = "high"\n'
      config_path.write_text(saved)
      with patch.object(cli.config, "CONFIG_PATH", config_path):
        result = CliRunner().invoke(cli._app, ["models", "get-default"])

      self.assertEqual(result.exit_code, 1)
      self.assertNotIsInstance(result.exception, ValueError)
      output = " ".join(result.output.split())
      self.assertIn("Imagen 4 was retired", output)
      self.assertIn("genimg models set-default gdm:nb2", output)
      self.assertIn("genimg models clear-default", output)
      self.assertEqual(config_path.read_text(), saved)


class GenerationMetadataTests(unittest.TestCase):
  def test_grid_failure_keeps_image_metadata(self) -> None:
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      out_path = root / "image.png"
      meta_dir = root / "metadata"
      grid_dir = root / "grids"

      def fake_generate(*args, **kwargs) -> GenerateResult:
        paths = [out_path.with_name("image_1.png"), out_path.with_name("image_2.png")]
        for path in paths:
          path.write_bytes(b"png")
        return GenerateResult(paths=paths, model_used="gpt-image-2")

      with (
        patch.object(cli.config, "load", return_value={}),  # isolate from the dev's real saved defaults
        patch.object(metadata, "META_DIR", meta_dir),
        patch.object(metadata, "GRID_DIR", grid_dir),
        patch.object(metadata, "make_id", return_value="test-gen"),
        patch.object(cli, "run_generate", side_effect=fake_generate),
        patch.object(cli.grid_module, "render", side_effect=RuntimeError("grid failed")),
      ):
        result = runner.invoke(cli._app, ["prompt", "-m", "oai:gi2", "-n", "2", "-g", "-o", str(out_path)])

      self.assertNotEqual(result.exit_code, 0)
      meta_path = meta_dir / "test-gen.json"
      self.assertTrue(meta_path.exists())
      payload = json.loads(meta_path.read_text())
      self.assertEqual([Path(item["path"]).name for item in payload["outputs"]], ["image_1.png", "image_2.png"])
      self.assertNotIn("grid", payload)

  def test_generation_name_is_trimmed_and_saved(self) -> None:
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      out_path = root / "image.png"
      meta_dir = root / "metadata"

      def fake_generate(*args, **kwargs) -> GenerateResult:
        out_path.write_bytes(b"png")
        return GenerateResult(paths=[out_path], model_used="gpt-image-2")

      with (
        patch.object(cli.config, "load", return_value={}),
        patch.object(metadata, "META_DIR", meta_dir),
        patch.object(metadata, "make_id", return_value="test-gen"),
        patch.object(cli, "run_generate", side_effect=fake_generate),
      ):
        result = runner.invoke(cli._app, [
          "prompt", "-m", "oai:gi2", "--name", "  deep-between  ", "-o", str(out_path),
        ])

      self.assertEqual(result.exit_code, 0, result.output)
      payload = json.loads((meta_dir / "test-gen.json").read_text())
      self.assertEqual(payload["name"], "deep-between")
      self.assertIn("deep-between", result.output)

  def test_blank_generation_name_is_unset(self) -> None:
    runner = CliRunner()
    with (
      patch.object(cli.config, "load", return_value={}),
      patch.object(cli.auth_resolve, "info", return_value=AuthInfo("direct", "env", "-", "OPENAI_API_KEY", True)),
    ):
      result = runner.invoke(cli._app, [
        "prompt", "-m", "oai:gi2", "--name", "   ", "--dry-run",
      ])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertNotIn("name      ", result.output)

  def test_multiline_generation_name_is_rejected(self) -> None:
    runner = CliRunner()
    with patch.object(cli.config, "load", return_value={}):
      result = runner.invoke(cli._app, [
        "prompt", "-m", "oai:gi2", "--name", "one\ntwo", "--dry-run",
      ])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("--name must be one line", result.output)


if __name__ == "__main__":
  unittest.main()


class ProfileFlagTests(unittest.TestCase):
  def test_unknown_profile_fails_before_dry_run_banner(self) -> None:
    with patch.object(cli.config, "load", return_value={"profiles": {"work": {"provider": "openai", "auth": "direct"}}}):
      result = CliRunner().invoke(cli._app, ["prompt", "-m", "oai:gi2", "--profile", "nope", "--dry-run"])
    self.assertEqual(result.exit_code, 1, result.output)
    output = " ".join(result.output.split())
    self.assertIn("no profile 'nope'", output)
    self.assertIn("Known: work", output)
    self.assertNotIn("genimg openai", output)

  def test_named_profile_shows_in_banner(self) -> None:
    cfg = {"profiles": {"work": {"provider": "openai", "auth": "azure", "endpoint": "https://x.openai.azure.com"}}}
    with patch.object(cli.config, "load", return_value=cfg), \
         patch.dict("os.environ", {"AZURE_OPENAI_API_KEY": "k"}):
      result = CliRunner().invoke(cli._app, ["prompt", "-m", "oai:gi2", "--profile", "work", "--dry-run"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIn("openai/azure@work", result.output)


class AuthFlagTests(unittest.TestCase):
  def test_auth_direct_forces_openai_api_key_mode(self) -> None:
    with patch.object(cli.config, "load", return_value={}), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "k", "AZURE_OPENAI_ENDPOINT": "https://x.openai.azure.com"}):
      result = CliRunner().invoke(cli._app, ["prompt", "-m", "oai:gi2", "--auth", "direct", "--dry-run"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIn("genimg openai/direct ", result.output)

  def test_auth_native_is_rejected(self) -> None:
    with patch.object(cli.config, "load", return_value={}), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "k"}):
      result = CliRunner().invoke(cli._app, ["prompt", "-m", "oai:gi2", "--auth", "native", "--dry-run"])
    self.assertEqual(result.exit_code, 1, result.output)
    self.assertIn("--auth must be one of azure, direct, got 'native'", " ".join(result.output.split()))


class ModelOptionDryRunTests(unittest.TestCase):
  """Drive the real `prompt --dry-run` path: alias resolution, capabilities and validation."""

  def _dry_run(self, *args: str) -> tuple[int, str]:
    with patch.object(cli.config, "load", return_value={}), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "k"}):
      result = CliRunner().invoke(cli._app, ["prompt", *args, "--dry-run"])
    return result.exit_code, " ".join(result.output.split())

  def test_nb2_lite_accepts_both_thinking_levels(self) -> None:
    for level in ("minimal", "high"):
      exit_code, output = self._dry_run("-m", "gdm:nb2-lite", "--thinking", level)
      self.assertEqual(exit_code, 0, output)
      self.assertIn(f"thinking={level}", output)

  def test_gpt_image_1_family_rejects_sizes_beyond_the_1024_square(self) -> None:
    models = (("oai:gi1", "gpt-image-1"), ("oai:gi1-mini", "gpt-image-1-mini"),
              ("oai:gi1.5", "gpt-image-1.5"))
    for alias, model_id in models:
      for flags in (("-r", "2K"), ("-a", "4:3")):
        exit_code, output = self._dry_run("-m", alias, *flags)
        self.assertEqual(exit_code, 1, output)
        self.assertIn(f"{model_id} takes only 1K 1:1 (1024x1024)", output)
        self.assertNotIn("dry-run: no API call made", output)

  def test_gpt_image_1_default_size_is_the_1024_square(self) -> None:
    exit_code, output = self._dry_run("-m", "oai:gi1")
    self.assertEqual(exit_code, 0, output)
    self.assertIn("→ 1024x1024", output)


class CorruptConfigTests(unittest.TestCase):
  def test_corrupt_config_toml_is_reported_not_clobbered(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      config_path = Path(td) / "config.toml"
      config_path.write_text("default_model = ")
      with patch.object(cli.config, "CONFIG_PATH", config_path):
        result = CliRunner().invoke(cli._app, ["models", "set-default", "gdm:nb2"], catch_exceptions=True)
      self.assertIsInstance(result.exception, cli.config.ConfigError)
      self.assertEqual(config_path.read_text(), "default_model = ")


class StandaloneGridTests(unittest.TestCase):
  FOX = Path(__file__).resolve().parents[1] / "docs" / "assets" / "fox-1.webp"

  def test_a_directory_expands_to_the_images_inside_it(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      folder = Path(td) / "takes"
      folder.mkdir()
      for name in ("a.webp", "b.webp"):
        (folder / name).write_bytes(self.FOX.read_bytes())
      (folder / "notes.txt").write_text("not an image")
      out = Path(td) / "grid.html"
      result = CliRunner().invoke(cli._app, ["grid", str(folder), "--output", str(out)])

      self.assertEqual(result.exit_code, 0, result.output)
      self.assertIn("(2 images)", " ".join(result.output.split()))
      html = out.read_text()
      self.assertIn("a.webp", html)
      self.assertIn("b.webp", html)
      self.assertNotIn("notes.txt", html)

  def test_a_file_that_is_not_an_image_is_refused_cleanly(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      script = Path(td) / "mk.py"
      script.write_text("print('hi')\n")
      out = Path(td) / "grid.html"
      result = CliRunner().invoke(cli._app, ["grid", str(script), "--output", str(out)])

      self.assertEqual(result.exit_code, 1)
      self.assertIsInstance(result.exception, SystemExit)
      self.assertIn("not an image", result.output)
      self.assertFalse(out.exists())

  def test_a_directory_without_images_is_refused_cleanly(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      out = Path(td) / "grid.html"
      result = CliRunner().invoke(cli._app, ["grid", td, "--output", str(out)])

      self.assertEqual(result.exit_code, 1)
      self.assertIsInstance(result.exception, SystemExit)
      self.assertIn("no images found", result.output)
      self.assertFalse(out.exists())
