from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from genimg import cli, metadata
from genimg.interfaces import GenerateRequest, GenerateResult, IImageGen
from genimg.providers.google import GeminiImageGen
from genimg.providers.openai import OpenAIImageGen

_PNG = base64.b64encode(b"png").decode()


class _FakeGen(IImageGen):
  def __init__(self) -> None:
    self.single_calls = 0
    self.batch_calls = 0

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    self.single_calls += 1
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")
    return out

  def _generate_batch(self, req: GenerateRequest) -> list[Path]:
    self.batch_calls += 1
    req.output.parent.mkdir(parents=True, exist_ok=True)
    paths = [self.numbered_path(req.output, i, req.n) for i in range(req.n)]
    for p in paths:
      p.write_bytes(b"png")
    return paths

  def probe(self, model: str, region: str | None = None):
    raise NotImplementedError


class ModeDispatchTests(unittest.TestCase):
  def test_batch_mode_dispatches_one_batch_call(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      gen = _FakeGen()
      result = gen.generate(GenerateRequest(
        prompt="p", output=Path(td) / "img.png", model="fake", n=3, mode="batch"))
    self.assertEqual((gen.batch_calls, gen.single_calls), (1, 0))
    self.assertEqual(len(result.paths), 3)

  def test_default_mode_fans_out(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      gen = _FakeGen()
      gen.generate(GenerateRequest(prompt="p", output=Path(td) / "img.png", model="fake", n=3))
    self.assertEqual((gen.batch_calls, gen.single_calls), (0, 3))

  def test_base_class_batch_is_unsupported(self) -> None:
    class _NoBatch(IImageGen):
      def _generate_single_image(self, req, i):
        raise AssertionError("should not be called")
      def probe(self, model, region=None):
        raise NotImplementedError

    with tempfile.TemporaryDirectory() as td:
      req = GenerateRequest(prompt="p", output=Path(td) / "img.png", model="fake", n=2, mode="batch")
      with self.assertRaises(RuntimeError):
        _NoBatch().generate(req)


class OpenAIBatchTests(unittest.TestCase):
  def test_openai_has_no_batch_path(self) -> None:
    # gpt-image n>1 returns near-duplicate independent samples (verified live), so the
    # provider deliberately has no batch implementation — the base class refuses.
    client = MagicMock()
    client.images.generate.return_value = SimpleNamespace(
      data=[SimpleNamespace(b64_json=_PNG)])
    with tempfile.TemporaryDirectory() as td, \
         patch("genimg.providers.openai.get_client", return_value=client):
      req = GenerateRequest(prompt="p", output=Path(td) / "img.png",
                            model="gpt-image-2", n=3, mode="batch")
      with self.assertRaises(RuntimeError):
        OpenAIImageGen().generate(req)
    client.images.generate.assert_not_called()  # refused before any spend


class GeminiBatchTests(unittest.TestCase):
  def _client_returning(self, n_images: int) -> MagicMock:
    def part() -> MagicMock:
      p = MagicMock()
      p.inline_data = object()
      p.as_image.return_value.save.side_effect = lambda out: Path(out).write_bytes(b"png")
      return p
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
      parts=[part() for _ in range(n_images)])
    return client

  def test_batch_is_one_request_asking_for_n_images(self) -> None:
    client = self._client_returning(3)
    with tempfile.TemporaryDirectory() as td, \
         patch("genimg.providers.google.get_client", return_value=client):
      req = GenerateRequest(prompt="a fox", output=Path(td) / "img.png",
                            model="gemini-3.1-flash-image-preview", n=3, mode="batch")
      result = GeminiImageGen().generate(req)
      self.assertEqual(len(result.paths), 3)
    client.models.generate_content.assert_called_once()
    sent_prompt = client.models.generate_content.call_args.kwargs["contents"][0]
    self.assertIn("Generate exactly 3 separate images", sent_prompt)
    self.assertIn("a fox", sent_prompt)
    self.assertNotIn("no two alike", sent_prompt)  # diversity clause only with -d

  def test_batch_diverse_instructs_model_to_differentiate(self) -> None:
    client = self._client_returning(2)
    with tempfile.TemporaryDirectory() as td, \
         patch("genimg.providers.google.get_client", return_value=client):
      req = GenerateRequest(prompt="a fox", output=Path(td) / "img.png",
                            model="gemini-3.1-flash-image-preview", n=2, mode="batch", diverse=True)
      GeminiImageGen().generate(req)
    sent_prompt = client.models.generate_content.call_args.kwargs["contents"][0]
    self.assertIn("no two alike", sent_prompt)

  def test_batch_keeps_partial_results(self) -> None:
    client = self._client_returning(2)  # model returned 2 of 4
    with tempfile.TemporaryDirectory() as td, \
         patch("genimg.providers.google.get_client", return_value=client):
      req = GenerateRequest(prompt="a fox", output=Path(td) / "img.png",
                            model="gemini-3.1-flash-image-preview", n=4, mode="batch")
      result = GeminiImageGen().generate(req)
      self.assertEqual(len(result.paths), 2)


class ModeCliTests(unittest.TestCase):
  def _invoke(self, args: list[str]):
    runner = CliRunner()
    captured: list[GenerateRequest] = []
    with tempfile.TemporaryDirectory() as td:
      out_path = Path(td) / "image.png"
      meta_dir = Path(td) / "metadata"

      def fake_generate(req: GenerateRequest, **kwargs) -> GenerateResult:
        captured.append(req)
        paths = [IImageGen.numbered_path(out_path, i, req.n) for i in range(req.n)]
        for p in paths:
          p.write_bytes(b"png")
        return GenerateResult(paths=paths, model_used="m")

      with (
        patch.object(cli.config, "load", return_value={}),  # isolate from the dev's real saved defaults
        patch.object(metadata, "META_DIR", meta_dir),
        patch.object(metadata, "make_id", return_value="test-gen"),
        patch.object(cli, "run_generate", side_effect=fake_generate),
      ):
        result = runner.invoke(cli._app, [*args, "-o", str(out_path)])
        payload = None
        meta_path = meta_dir / "test-gen.json"
        if meta_path.exists():
          payload = json.loads(meta_path.read_text())
    return result, captured, payload

  def test_no_diverse_hint_in_batch_mode(self) -> None:
    # -d/--deltas guidance doesn't apply to batch submissions (roborev 3618, Low)
    result, _, _ = self._invoke(["p", "-m", "gdm:nb2", "-n", "3", "--mode", "batch"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertNotIn("near-duplicates", result.output)

  def test_mode_batch_plumbs_through_and_is_recorded(self) -> None:
    result, captured, payload = self._invoke(["p", "-m", "gdm:nb2", "-n", "3", "--mode", "batch"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(captured[0].mode, "batch")
    self.assertEqual(payload["mode"], "batch")

  def test_mode_batch_rejected_on_openai(self) -> None:
    result, captured, _ = self._invoke(["p", "-m", "oai:gi2", "-n", "3", "--mode", "batch"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("wasted spend", result.output)
    self.assertEqual(captured, [])  # refused before any API call

  def test_default_mode_is_auto(self) -> None:
    result, captured, payload = self._invoke(["p", "-m", "oai:gi2", "-n", "2"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIsNone(captured[0].mode)
    self.assertEqual(payload["mode"], "auto")

  def test_bad_mode_value_errors(self) -> None:
    result, captured, _ = self._invoke(["p", "-m", "oai:gi2", "--mode", "sideways"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("--mode must be", result.output)
    self.assertEqual(captured, [])

  def test_batch_diverse_openai_errors(self) -> None:
    result, captured, _ = self._invoke(["p", "-m", "oai:gi2", "-n", "4", "-d", "--mode", "batch"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("wasted spend", result.output)  # blanket OpenAI batch rejection fires first
    self.assertEqual(captured, [])

  def test_batch_diverse_imagen_errors(self) -> None:
    result, captured, _ = self._invoke(["p", "-m", "gdm:imagen4", "-n", "4", "-d", "--mode", "batch"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("Gemini image models only", result.output)
    self.assertEqual(captured, [])

  def test_batch_diverse_gemini_skips_prompt_deltas(self) -> None:
    result, captured, payload = self._invoke(["p", "-m", "gdm:nb2", "-n", "3", "-d", "--mode", "batch"])
    self.assertEqual(result.exit_code, 0, result.output)
    req = captured[0]
    self.assertEqual((req.mode, req.diverse), ("batch", True))
    self.assertIsNone(req.prompt_variants)  # model-side diversity, not per-request deltas
    self.assertTrue(payload["diverse"])
    self.assertNotIn("prompt_delta", payload["outputs"][0])


if __name__ == "__main__":
  unittest.main()
