from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from rich.console import Console

from genimg import cli


def _validate(**overrides) -> None:
  defaults = dict(
    provider="openai", quality=None, region=None, project=None, auth=None,
    resolution=None, aspect_ratio=None, refs=[], input=None, model_id="gpt-image-2",
  )
  defaults.update(overrides)
  cli._validate_provider_flags(**defaults)


class ValidationMatrixTests(unittest.TestCase):
  def setUp(self) -> None:
    # Silence _die's Rich output so the suite stays quiet.
    self._patch = patch.object(cli, "console", Console(file=io.StringIO()))
    self._patch.start()
    self.addCleanup(self._patch.stop)
    self.tmp = Path(tempfile.mkdtemp())
    self.png = self.tmp / "a.png"
    self.png.write_bytes(b"x")

  # --- provider/flag incompatibilities ---
  def test_quality_on_google_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="google", quality="high", model_id="gemini-2.5-flash-image")

  def test_resolution_on_gemini_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="google", resolution="2K", model_id="gemini-2.5-flash-image")

  def test_resolution_on_imagen_ok(self) -> None:
    _validate(provider="google", resolution="2K", model_id="imagen-4.0-generate-001")

  def test_imagen_with_input_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="google", model_id="imagen-4.0-generate-001", input=self.png)

  def test_region_on_openai_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", region="us-central1")

  def test_auth_on_google_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="google", auth="direct", model_id="gemini-2.5-flash-image")

  # --- OpenAI size combos (derived from _SIZE_MAP) ---
  def test_openai_1k_16_9_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", resolution="1K", aspect_ratio="16:9")

  def test_openai_4k_4_3_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", resolution="4K", aspect_ratio="4:3")

  def test_openai_2k_16_9_ok(self) -> None:
    _validate(provider="openai", resolution="2K", aspect_ratio="16:9")

  # --- value validity (runs before the size check) ---
  def test_bad_resolution_value_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", resolution="8K")

  def test_bad_aspect_value_rejected(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", aspect_ratio="2:1")

  # --- provider-neutral + OpenAI input checks ---
  def test_missing_input_rejected_for_google(self) -> None:
    with self.assertRaises(typer.Exit):
      _validate(provider="google", model_id="gemini-2.5-flash-image", input=Path("/nope/x.png"))

  def test_openai_bad_extension_rejected(self) -> None:
    bad = self.tmp / "a.gif"
    bad.write_bytes(b"x")
    with self.assertRaises(typer.Exit):
      _validate(provider="openai", input=bad)

  def test_valid_openai_input_ok(self) -> None:
    _validate(provider="openai", input=self.png)


if __name__ == "__main__":
  unittest.main()
