from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from genimg import cli, diversify, metadata
from genimg import grid as grid_module
from genimg.interfaces import GenerateRequest, GenerateResult, IImageGen


class DiversifyTests(unittest.TestCase):
  def test_pool_covers_max_n(self) -> None:
    # CLI caps -n at 10; index 0 is the base prompt, so 9 deltas must exist.
    self.assertGreaterEqual(len(diversify.DELTAS), 9)

  def test_pick_deltas_shape(self) -> None:
    deltas = diversify.pick_deltas(4, rng=random.Random(0))
    self.assertEqual(len(deltas), 4)
    self.assertIsNone(deltas[0])
    picks = deltas[1:]
    self.assertEqual(len(set(picks)), 3)  # sampled without replacement
    for d in picks:
      self.assertIn(d, diversify.DELTAS)

  def test_pick_deltas_rejects_oversized_n(self) -> None:
    with self.assertRaises(ValueError):
      diversify.pick_deltas(len(diversify.DELTAS) + 2)

  def test_apply(self) -> None:
    self.assertEqual(diversify.apply("a fox", None), "a fox")
    self.assertEqual(diversify.apply("a fox", "isometric 3D perspective"),
                     "a fox — isometric 3D perspective")


class _FakeGen(IImageGen):
  """Records the prompt each single-image call received."""
  def __init__(self) -> None:
    self.prompts_by_index: dict[int, str] = {}

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    self.prompts_by_index[i] = req.prompt
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")
    return out

  def probe(self, model: str, region: str | None = None):
    raise NotImplementedError


class PromptVariantPlumbingTests(unittest.TestCase):
  def test_generate_uses_per_index_variants(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      gen = _FakeGen()
      req = GenerateRequest(
        prompt="base", output=Path(td) / "img.png", model="fake", n=3,
        prompt_variants=["base", "base — v2", "base — v3"],
      )
      result = gen.generate(req)
    self.assertEqual(gen.prompts_by_index, {0: "base", 1: "base — v2", 2: "base — v3"})
    self.assertEqual(len(result.paths), 3)

  def test_generate_without_variants_uses_base_prompt(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      gen = _FakeGen()
      gen.generate(GenerateRequest(prompt="base", output=Path(td) / "img.png", model="fake", n=2))
    self.assertEqual(gen.prompts_by_index, {0: "base", 1: "base"})


class DiverseCliTests(unittest.TestCase):
  def _invoke_diverse(self, args: list[str]):
    """Run the CLI with generation mocked; returns (result, captured requests, meta_dir)."""
    runner = CliRunner()
    captured: list[GenerateRequest] = []
    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      out_path = root / "image.png"
      meta_dir = root / "metadata"

      def fake_generate(req: GenerateRequest, **kwargs) -> GenerateResult:
        captured.append(req)
        paths = [IImageGen.numbered_path(out_path, i, req.n) for i in range(req.n)]
        for p in paths:
          p.write_bytes(b"png")
        return GenerateResult(paths=paths, model_used="gpt-image-2")

      with (
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

  def test_diverse_without_n_errors_fast(self) -> None:
    result, captured, _ = self._invoke_diverse(["prompt", "-m", "oai:gi2", "-d"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("--diverse requires -n >= 2", result.output)
    self.assertEqual(captured, [])  # no API call

  def test_diverse_with_n1_errors_fast(self) -> None:
    result, captured, _ = self._invoke_diverse(["prompt", "-m", "oai:gi2", "-n", "1", "-d"])
    self.assertEqual(result.exit_code, 1)
    self.assertIn("--diverse requires -n >= 2", result.output)
    self.assertEqual(captured, [])

  def test_diverse_passes_distinct_variants_and_records_deltas(self) -> None:
    result, captured, payload = self._invoke_diverse(
      ["a SINGLE fox logo", "-m", "oai:gi2", "-n", "3", "-d"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(len(captured), 1)
    variants = captured[0].prompt_variants
    self.assertEqual(len(variants), 3)
    self.assertEqual(variants[0], "a SINGLE fox logo")  # index 0 anchors the base prompt
    self.assertEqual(len(set(variants)), 3)  # all distinct
    for v in variants[1:]:
      self.assertTrue(v.startswith("a SINGLE fox logo — "))

    self.assertTrue(payload["diverse"])
    deltas = [o["prompt_delta"] for o in payload["outputs"]]
    self.assertIsNone(deltas[0])
    for d, o in zip(deltas[1:], payload["outputs"][1:]):
      self.assertIn(d, diversify.DELTAS)
      self.assertEqual(o["prompt_effective"], f"a SINGLE fox logo — {d}")

  def test_plain_n_stays_undiversified(self) -> None:
    result, captured, payload = self._invoke_diverse(["prompt", "-m", "oai:gi2", "-n", "2"])
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIsNone(captured[0].prompt_variants)
    self.assertFalse(payload["diverse"])
    self.assertNotIn("prompt_delta", payload["outputs"][0])


class DiverseGridTests(unittest.TestCase):
  def test_grid_surfaces_per_card_deltas(self) -> None:
    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      imgs = [root / "img_1.png", root / "img_2.png"]
      for p in imgs:
        p.write_bytes(b"png")
      meta = {
        "prompt": "a fox", "diverse": True,
        "outputs": [
          {"path": str(imgs[0]), "prompt_delta": None, "prompt_effective": "a fox"},
          {"path": str(imgs[1]), "prompt_delta": "isometric 3D perspective",
           "prompt_effective": "a fox — isometric 3D perspective"},
        ],
      }
      written, _ = grid_module.render(imgs, root / "grid.html", meta=meta)
      html_doc = written.read_text()
    self.assertIn("isometric 3D perspective", html_doc)
    self.assertIn("base prompt", html_doc)  # the anchor card is labelled too
    self.assertIn("per-card prompt deltas", html_doc)  # info panel row


if __name__ == "__main__":
  unittest.main()
