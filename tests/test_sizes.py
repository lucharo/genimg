from __future__ import annotations

import unittest
from pathlib import Path

from genimg.interfaces import GenerateRequest
from genimg.providers.openai import _SIZE_MAP, OpenAIImageGen


def _req(resolution=None, aspect_ratio=None, model="gpt-image-2") -> GenerateRequest:
  return GenerateRequest(
    prompt="x", output=Path("/tmp/x.png"), model=model,
    resolution=resolution, aspect_ratio=aspect_ratio,
  )


class OpenAISizeTests(unittest.TestCase):
  def test_defaults_to_1k_square(self) -> None:
    self.assertEqual(OpenAIImageGen()._size_for(_req()), "1024x1024")

  def test_2k_16_9(self) -> None:
    self.assertEqual(OpenAIImageGen()._size_for(_req("2K", "16:9")), "2048x1152")

  def test_unsupported_combo_raises(self) -> None:
    with self.assertRaises(RuntimeError):
      OpenAIImageGen()._size_for(_req("1K", "16:9"))

  def test_gpt_image_1_family_serves_only_the_1024_square(self) -> None:
    # Library callers bypass CLI validation, so the request builder must refuse too.
    gen = OpenAIImageGen()
    for model in ("gpt-image-1", "gpt-image-1-mini", "gpt-image-1.5", "gpt-image-1-2025-04-15"):
      self.assertEqual(gen._size_for(_req(model=model)), "1024x1024")
      with self.assertRaises(RuntimeError):
        gen._size_for(_req("2K", "1:1", model=model))

  def test_every_map_entry_round_trips(self) -> None:
    gen = OpenAIImageGen()
    for (res, ar), expected in _SIZE_MAP.items():
      self.assertEqual(gen._size_for(_req(res, ar)), expected)


if __name__ == "__main__":
  unittest.main()
