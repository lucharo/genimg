from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from genimg import metadata


class EmbedIntoImagesTest(unittest.TestCase):
  def test_preserves_existing_text_chunks(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "img.png"
      # A PNG that already carries provider-embedded text (e.g. from OpenAI).
      info = PngInfo()
      info.add_text("provider_chunk", "keep-me")
      Image.new("RGB", (4, 4), "white").save(path, pnginfo=info)

      metadata.embed_into_images({
        "prompt": "a cat",
        "model_id": "gpt-image-1",
        "provider": "openai",
        "outputs": [{"path": str(path)}],
      })

      text = getattr(Image.open(path), "text", {})
      self.assertEqual(text["provider_chunk"], "keep-me")  # upstream preserved
      self.assertEqual(text["prompt"], "a cat")            # genimg key added
      self.assertEqual(text["genimg.provider"], "openai")

  def test_diverse_outputs_embed_their_own_effective_prompt(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      base = Path(d) / "img_1.png"
      varied = Path(d) / "img_2.png"
      for p in (base, varied):
        Image.new("RGB", (4, 4), "white").save(p)

      metadata.embed_into_images({
        "prompt": "a cat",
        "model_id": "gpt-image-2",
        "provider": "openai",
        "outputs": [
          {"path": str(base), "prompt_delta": None, "prompt_effective": "a cat"},
          {"path": str(varied), "prompt_delta": "isometric 3D perspective",
           "prompt_effective": "a cat — isometric 3D perspective"},
        ],
      })

      base_text = getattr(Image.open(base), "text", {})
      self.assertEqual(base_text["prompt"], "a cat")
      self.assertNotIn("genimg.prompt_delta", base_text)

      varied_text = getattr(Image.open(varied), "text", {})
      self.assertEqual(varied_text["prompt"], "a cat — isometric 3D perspective")
      self.assertEqual(varied_text["parameters"], "a cat — isometric 3D perspective")
      self.assertEqual(varied_text["genimg.prompt_delta"], "isometric 3D perspective")

  def test_thinking_level_is_recorded_in_sidecar_and_png_params(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "img.png"
      Image.new("RGB", (4, 4), "white").save(path)
      spec = SimpleNamespace(
        model_id="gemini-3.1-flash-image",
        provider="google",
        region="global",
      )

      meta = metadata.build(
        gen_id="test", prompt="a cat", alias="gdm:nb2", spec=spec,
        paths=[path], n=1, cost_usd=0.01, thinking_level="high",
      )
      metadata.embed_into_images(meta)

      self.assertEqual(meta["thinking_level"], "high")
      params = getattr(Image.open(path), "text", {})["genimg.params"]
      self.assertEqual(__import__("json").loads(params), {"n": 1, "thinking_level": "high"})


if __name__ == "__main__":
  unittest.main()
