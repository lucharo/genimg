from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
  unittest.main()
