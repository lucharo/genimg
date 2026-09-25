from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from genimg import grid, metadata


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

  def test_info_panel_shows_edit_input_and_ordered_references(self) -> None:
    html = self._render(meta=self._meta(
      input="/Users/private-user/confidential-project/original-room.jpg",
      refs=["/Users/private-user/confidential-project/approved-concept.png", "/Users/private-user/confidential-project/palette.png"],
    ))
    self.assertIn(">edit input<", html)
    self.assertIn("original-room.jpg", html)
    self.assertIn(">reference 1<", html)
    self.assertIn(">reference 2<", html)
    self.assertLess(html.index("approved-concept.png"), html.index("palette.png"))
    self.assertNotIn("private-user", html)
    self.assertNotIn("confidential-project", html)

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

  def test_filenames_are_html_escaped_in_grid_cards(self) -> None:
    # _js() protects the <script> block, but card labels/filenames pass through
    # innerHTML at runtime — they must go through esc() or an HTML filename injects.
    html = self._render()
    self.assertIn("function esc(", html)
    self.assertIn("${esc(im.filename)}", html)
    self.assertIn("${esc(im.label)}", html)
    self.assertIn("${esc(im.src)}", html)

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


def _render_n(root: Path, n: int, **kwargs) -> str:
  imgs = [root / f"t_{i}.png" for i in range(1, n + 1)]
  for p in imgs:
    _make_png(p)
  out, _ = grid.render(imgs, root / "grid.html", **kwargs)
  return out.read_text()


class TournamentEntryTests(unittest.TestCase):
  def setUp(self) -> None:
    self.root = Path(tempfile.mkdtemp())
    # Standalone grids look models up in the sidecars; never read the host's ~/.genimg.
    patcher = patch.object(metadata, "META_DIR", self.root / "metadata")
    patcher.start()
    self.addCleanup(patcher.stop)

  def test_entry_and_dialog_offered_from_3_to_20_images(self) -> None:
    for n in (3, 20):
      html = _render_n(self.root, n)
      self.assertIn('id="btn-tourney"', html)
      self.assertIn('<dialog id="tourney"', html)

  def test_no_tournament_below_3_or_above_20_images(self) -> None:
    for n in (2, 21):
      html = _render_n(self.root, n)
      self.assertNotIn('id="btn-tourney"', html)
      self.assertNotIn('<dialog id="tourney"', html)

  def test_explainer_is_a_focusable_tooltip_with_the_pick_count(self) -> None:
    html = _render_n(self.root, 8)
    self.assertIn('<button type="button" class="t-info" aria-label="What is the tournament?" '
                  'aria-describedby="t-tip">i</button>', html)
    self.assertIn('role="tooltip" id="t-tip"', html)
    self.assertIn("8 images take 7 picks, about 1 min.", html)

  def test_top3_costs_no_extra_match_with_3_images(self) -> None:
    self.assertIn("Top 3 <small>no extra match</small>", _render_n(self.root, 3))
    self.assertIn("Top 3 <small>+1 match</small>", _render_n(self.root, 4))

  def test_generation_grid_cards_carry_the_generation_model(self) -> None:
    meta = {"id": "20260925_x", "alias": "oai:gi2", "model_id": "gpt-image-2", "provider": "openai",
            "prompt": "p", "cost_usd_estimated": 0.1}
    html = _render_n(self.root, 3, meta=meta)
    self.assertEqual(_images(html)[0], {
      "src": _images(html)[0]["src"], "label": "#1", "filename": "t_1.png",
      "copyText": "I choose #1 (t_1.png)", "delta": "", "model": "oai:gi2", "provider": "openai"})
    self.assertIn('const GENERATION_ID = "20260925_x";', html)

  def test_standalone_grid_cards_take_each_model_from_its_sidecar(self) -> None:
    gen, mine = self.root / "gen_1.png", self.root / "mine.png"
    for p in (gen, mine, self.root / "other.png"):
      _make_png(p)
    metadata.META_DIR.mkdir()
    (metadata.META_DIR / "g.json").write_text(json.dumps(
      {"alias": "gdm:nb2", "provider": "gemini", "outputs": [{"path": str(gen)}]}))
    out, _ = grid.render([gen, mine, self.root / "other.png"], self.root / "grid.html")
    images = _images(out.read_text())
    self.assertEqual([(im["model"], im["provider"]) for im in images],
                     [("gdm:nb2", "gemini"), (None, None), (None, None)])


def _images(html: str) -> list[dict]:
  start = html.index("const IMAGES = ") + len("const IMAGES = ")
  return json.loads(html[start:html.index(";\n", start)])


@unittest.skipUnless(shutil.which("node"), "node runs the bracket core (GitHub runners ship it)")
class TournamentBracketTests(unittest.TestCase):
  """Runs the page's own bracket code, cut from the rendered HTML, under node."""

  @classmethod
  def setUpClass(cls) -> None:
    with tempfile.TemporaryDirectory() as td, patch.object(metadata, "META_DIR", Path(td) / "m"):
      html = _render_n(Path(td), 3)
    cls.core = html[html.index("// <tourney-core>"):html.index("// </tourney-core>")]

  def _run(self, harness: str):
    proc = subprocess.run(["node", "-e", self.core + "\n" + harness],
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)

  # Plays a whole tournament where the lower id always wins; ids are offset and shuffled so the
  # test proves the bracket hands back the ids it was given.
  _PLAY = """
    function play(n, top3){
      const order=[...Array(n).keys()].sort((x,y)=>(x%2)-(y%2)||y-x).map(i=>100+i);
      const picks=[];let s;
      while(!(s=bracket(order,picks,top3)).done)picks.push(Math.min(s.current.a,s.current.b));
      return {picks:picks.length,total:s.total,ranking:s.ranking,rounds:s.played.map(m=>m.round)};
    }
  """

  def test_a_winner_takes_n_minus_1_picks_for_3_to_20_images(self) -> None:
    got = self._run(self._PLAY + "console.log(JSON.stringify([...Array(18).keys()].map(i=>play(i+3,false))))")
    self.assertEqual([(g["picks"], g["total"]) for g in got], [(n - 1, n - 1) for n in range(3, 21)])
    self.assertEqual([g["ranking"][0] for g in got], [100] * 18)

  def test_top3_adds_one_pick_from_4_images_and_none_at_3(self) -> None:
    got = self._run(self._PLAY + "console.log(JSON.stringify([...Array(18).keys()].map(i=>play(i+3,true))))")
    self.assertEqual([g["picks"] for g in got], [2] + [n for n in range(4, 21)])
    for n, g in zip(range(3, 21), got):
      self.assertEqual(len(set(g["ranking"])), 3, n)
      self.assertTrue(set(g["ranking"]) <= set(range(100, 100 + n)), n)

  def test_eight_images_play_quarterfinals_semifinals_final(self) -> None:
    got = self._run(self._PLAY + "console.log(JSON.stringify([play(8,false),play(8,true)]))")
    self.assertEqual(got[0]["rounds"], ["Quarterfinal"] * 4 + ["Semifinal"] * 2 + ["Final"])
    self.assertEqual(got[1]["rounds"], ["Quarterfinal"] * 4 + ["Semifinal"] * 2 + ["Final", "Third place"])

  def test_five_images_give_byes_so_only_one_first_round_match_is_played(self) -> None:
    got = self._run(self._PLAY + "console.log(JSON.stringify(play(5,false)))")
    self.assertEqual(got["rounds"], ["Quarterfinal", "Semifinal", "Semifinal", "Final"])

  def test_a_pick_that_is_not_in_the_current_match_is_not_consumed(self) -> None:
    got = self._run("const s=bracket([0,1,2,3],[2],false);"
                    "console.log(JSON.stringify({used:s.used,current:s.current,done:s.done}))")
    self.assertEqual(got, {"used": 0, "current": {"a": 0, "b": 1, "round": "Semifinal"}, "done": False})


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
