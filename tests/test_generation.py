from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from genimg import cli
from genimg.auth.base import AuthInfo
from genimg.interfaces import GenerateRequest, IImageGen, ProbeResult


class NoDefaultModelTests(unittest.TestCase):
  def test_no_model_and_no_default_errors(self) -> None:
    runner = CliRunner()
    with patch.object(cli.config, "load", return_value={}):
      result = runner.invoke(cli._app, ["a prompt", "--dry-run"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("no model specified", " ".join(result.output.split()))

  def test_incompatible_global_size_defaults_are_ignored_for_selected_model(self) -> None:
    runner = CliRunner()
    config = {
      "default_resolution": "512",
      "default_aspect_ratio": "1:8",
    }
    with (
      patch.object(cli.config, "load", return_value=config),
      patch.object(cli.auth_resolve, "info", return_value=AuthInfo("vertex", "env", "-", "GOOGLE_APPLICATION_CREDENTIALS", True)),
    ):
      result = runner.invoke(cli._app, ["a prompt", "-m", "gdm:nbp", "--dry-run"])

    self.assertEqual(result.exit_code, 0, result.output)
    params_line = next(line for line in result.output.splitlines() if "params" in line)
    self.assertNotIn("r=512", params_line)
    self.assertNotIn("a=1:8", params_line)

  def test_retired_imagen_alias_explains_the_supported_replacement(self) -> None:
    runner = CliRunner()
    with patch.object(cli.config, "load", return_value={}):
      result = runner.invoke(cli._app, ["a prompt", "-m", "gdm:imagen4", "--dry-run"])

    self.assertEqual(result.exit_code, 1)
    self.assertIn("Imagen 4 was retired", result.output)
    self.assertIn("gdm:nb2", result.output)


class DryRunProvenanceTests(unittest.TestCase):
  def test_input_and_ordered_references_are_labelled(self) -> None:
    root = Path(tempfile.mkdtemp())
    edit_input = root / "original.png"
    first_ref = root / "approved-concept.png"
    second_ref = root / "palette.png"
    for path in (edit_input, first_ref, second_ref):
      path.write_bytes(b"x")

    with (
      patch.object(cli.config, "load", return_value={}),
      patch.object(cli.auth_resolve, "info", return_value=AuthInfo("vertex", "env", "-", "GOOGLE_APPLICATION_CREDENTIALS", True)),
    ):
      result = CliRunner().invoke(cli._app, [
        "preserve the room", str(first_ref), str(second_ref),
        "-i", str(edit_input), "-m", "gdm:nb2", "--dry-run",
      ])

    self.assertEqual(result.exit_code, 0, result.output)
    lines = [" ".join(line.split()) for line in result.output.splitlines()]
    self.assertIn(f"input {edit_input}", lines)
    self.assertIn(f"refs #1 {first_ref}", lines)
    self.assertIn(f"#2 {second_ref}", lines)
    self.assertLess(result.output.index(str(first_ref)), result.output.index(str(second_ref)))


class _FakeGen(IImageGen):
  """Succeeds for every index except those in `fail`."""

  def __init__(self, fail: set[int]):
    self.fail = fail

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    if i in self.fail:
      raise RuntimeError(f"boom-{i}")
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")
    return out

  def probe(self, model: str, region: str | None = None) -> ProbeResult:  # pragma: no cover
    return ProbeResult(model=model, status="working")


class PartialFailureTests(unittest.TestCase):
  def _req(self, n: int) -> GenerateRequest:
    out = Path(tempfile.mkdtemp()) / "o.png"
    return GenerateRequest(prompt="x", output=out, model="m", n=n)

  def test_partial_success_returns_paths_and_errors(self) -> None:
    result = _FakeGen(fail={1}).generate(self._req(3))
    self.assertEqual(len(result.paths), 2)          # indices 0 and 2 survived
    self.assertEqual(len(result.errors), 1)
    self.assertIn("boom-1", result.errors[0])

  def test_all_fail_raises(self) -> None:
    with self.assertRaises(RuntimeError):
      _FakeGen(fail={0, 1}).generate(self._req(2))

  def test_single_success_no_errors_field(self) -> None:
    result = _FakeGen(fail=set()).generate(self._req(1))
    self.assertEqual(len(result.paths), 1)
    self.assertEqual(result.errors, [])


class GoogleMkdirTests(unittest.TestCase):
  def test_creates_missing_output_parent(self) -> None:
    import genimg.providers.google as gp

    class FakeImg:
      def save(self, out) -> None:
        Path(out).write_bytes(b"PNG")

    class FakePart:
      inline_data = object()
      text = None

      def as_image(self) -> "FakeImg":
        return FakeImg()

    class FakeResp:
      parts = [FakePart()]

    class FakeModels:
      def generate_content(self, **kwargs) -> "FakeResp":
        return FakeResp()

    class FakeClient:
      models = FakeModels()

    out = Path(tempfile.mkdtemp()) / "new" / "sub" / "x.png"  # parent does not exist
    req = GenerateRequest(prompt="x", output=out, model="gemini-3.1-flash-image", n=1)
    with patch.object(gp, "get_client", return_value=FakeClient()):
      gp.GeminiImageGen()._generate_single_image(req, 0)
    self.assertTrue(out.exists())


class GoogleImageConfigTests(unittest.TestCase):
  def test_flash_image_high_thinking_reaches_provider_request(self) -> None:
    import genimg.providers.google as gp

    class FakeImg:
      def save(self, out) -> None:
        Path(out).write_bytes(b"PNG")

    class FakePart:
      inline_data = object()
      text = None

      def as_image(self) -> "FakeImg":
        return FakeImg()

    class FakeResp:
      parts = [FakePart()]

    captured = {}

    class FakeModels:
      def generate_content(self, **kwargs) -> "FakeResp":
        captured.update(kwargs)
        return FakeResp()

    class FakeClient:
      models = FakeModels()

    out = Path(tempfile.mkdtemp()) / "x.png"
    req = GenerateRequest(
      prompt="x", output=out, model="gemini-3.1-flash-image", n=1,
      thinking_level="high",
    )
    with patch.object(gp, "get_client", return_value=FakeClient()):
      gp.GeminiImageGen().generate(req)

    config = captured["config"].model_dump(exclude_none=True, mode="json")
    self.assertEqual(config["thinking_config"], {"thinking_level": "HIGH"})


if __name__ == "__main__":
  unittest.main()
