from __future__ import annotations

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

  def _meta(self, **over) -> dict:
    base = {
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
    base.update(over)
    return base

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

  def test_prompt_is_collapsible_and_hidden_by_default(self) -> None:
    html = self._render(meta=self._meta(), provider="openai", quality="medium")
    self.assertIn(">Show prompt<", html)
    self.assertIn("togglePrompt()", html)
    # The prompt box carries the hidden attribute (collapsed by default).
    self.assertIn('id="promptbox" class="promptbox" hidden', html)
    self.assertIn("a single centered fox", html)

  def test_info_panel_shows_model_and_single_cost(self) -> None:
    html = self._render(meta=self._meta(), provider="openai", quality="medium")
    self.assertIn('class="info"', html)
    self.assertIn("gpt-image-2", html)
    # Exactly one cost figure (harmonized) — the size/quality-aware meta value.
    self.assertEqual(html.count("$0.53"), 1)
    self.assertEqual(html.count("est. cost"), 1)
    # None-valued fields are omitted, not rendered.
    self.assertNotIn(">resolution<", html)

  def test_cost_prefers_meta_over_per_image_estimate(self) -> None:
    # meta cost ($0.53) wins over the renderer's per-image openai estimate ($0.05*3).
    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      imgs = [root / "c_1.png", root / "c_2.png", root / "c_3.png"]
      for p in imgs:
        _make_png(p)
      _, total = grid.render(imgs, root / "out.html",
                             provider="openai", quality="medium", meta=self._meta())
    self.assertAlmostEqual(total, 0.53)

  def test_no_panels_when_meta_absent(self) -> None:
    html = self._render()
    self.assertNotIn('class="info"', html)
    self.assertNotIn('class="promptbar"', html)

  def test_prompt_with_script_tag_is_neutralized(self) -> None:
    meta = {"prompt": "</script><script>alert(1)</script>", "model_id": "m", "provider": "p"}
    html = self._render(meta=meta)
    self.assertNotIn("<script>alert(1)</script>", html)

  def test_url_state_is_persisted_and_restored(self) -> None:
    # View, prompt, and carousel index round-trip through URL query params so
    # the page survives a refresh.
    html = self._render(meta=self._meta(), provider="openai", quality="medium")
    # Writes state via replaceState (not pushState — no history spam).
    self.assertIn("history.replaceState", html)
    self.assertNotIn("history.pushState", html)
    # Reads the three params back on load.
    self.assertIn("function restore(", html)
    self.assertIn("restore();", html)
    self.assertIn("q.get('view')", html)
    self.assertIn("q.get('prompt')", html)
    self.assertIn("q.get('i')", html)
    # State-changing handlers persist to the URL.
    self.assertIn("writeUrl()", html)
    # Carousel index is stored 1-based to match the visible counter.
    self.assertIn("p.set('i',String(curIdx+1))", html)


class EmbedMetadataTests(unittest.TestCase):
  def test_prompt_round_trips_into_png(self) -> None:
    from genimg import metadata

    with tempfile.TemporaryDirectory() as td:
      png = Path(td) / "img_1.png"
      _make_png(png)
      meta = {
        "id": "20260603_x",
        "prompt": "a teal origami crane",
        "model_id": "gpt-image-2",
        "provider": "openai",
        "n": 1,
        "quality": "high",
        "resolution": None,
        "aspect_ratio": "1:1",
        "outputs": [{"path": str(png)}],
      }
      metadata.embed_into_images(meta)
      with Image.open(png) as img:
        text = img.text  # type: ignore[attr-defined]
      self.assertEqual(text.get("prompt"), "a teal origami crane")
      self.assertEqual(text.get("genimg.model"), "gpt-image-2")
      self.assertEqual(text.get("genimg.provider"), "openai")
      self.assertEqual(text.get("genimg.id"), "20260603_x")
      self.assertIn("aspect_ratio", text.get("genimg.params", ""))
      # None-valued params are dropped from the embedded JSON.
      self.assertNotIn("resolution", text.get("genimg.params", ""))
      self.assertEqual(text.get("parameters"), "a teal origami crane")


if __name__ == "__main__":
  unittest.main()
