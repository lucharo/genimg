from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from genimg import grid


def _make_png(path: Path) -> None:
  Image.new("RGB", (8, 8), (123, 45, 67)).save(path)


class GridRenderTests(unittest.TestCase):
  def _render(self, **kwargs) -> str:
    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      imgs = [root / "a_1.png", root / "a_2.png", root / "a_3.png"]
      for p in imgs:
        _make_png(p)
      out, _ = grid.render(imgs, root / "grid.html", **kwargs)
      return out.read_text()

  def test_embeds_each_image_once(self) -> None:
    html = self._render()
    # Three images → three data URIs in the JS array, no duplication for carousel.
    self.assertEqual(html.count("data:image/png;base64,"), 3)

  def test_includes_carousel_controls(self) -> None:
    html = self._render()
    self.assertIn('id="carousel"', html)
    self.assertIn("setView('carousel')", html)
    self.assertIn("function step(", html)
    self.assertIn("ArrowLeft", html)

  def test_metadata_panel_shows_prompt_and_model(self) -> None:
    meta = {
      "prompt": "a single centered fox",
      "alias": "oai:gi2",
      "model_id": "gpt-image-2",
      "provider": "openai",
      "n": 3,
      "quality": "medium",
      "aspect_ratio": "16:9",
      "resolution": None,
      "time": "2026-06-03T10:22:07+00:00",
      "cost_usd_estimated": 0.53,
    }
    html = self._render(meta=meta, provider="openai", quality="medium")
    self.assertIn("a single centered fox", html)
    self.assertIn("gpt-image-2", html)
    self.assertIn("$0.53", html)
    # None-valued fields are omitted, not rendered as "None".
    self.assertNotIn("resolution:", html)

  def test_no_meta_panel_when_meta_absent(self) -> None:
    html = self._render()
    self.assertNotIn('class="meta"', html)

  def test_prompt_with_script_tag_is_neutralized(self) -> None:
    # A prompt containing </script> must not break out of the inline script.
    meta = {"prompt": "</script><script>alert(1)</script>", "model_id": "m", "provider": "p"}
    html = self._render(meta=meta)
    self.assertNotIn("<script>alert(1)</script>", html)


if __name__ == "__main__":
  unittest.main()
