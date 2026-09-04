from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from textual.content import Content
from textual.widgets import Static

from genimg.history_view import (
  HelpScreen,
  HistoryViewApp,
  copy_image_to_clipboard,
  flatten_entries,
  render_preview,
)


def _entry(root: Path, *, gen_id: str = "g1", outputs: int = 2) -> dict:
  paths = []
  for index in range(outputs):
    path = root / f"image-{index + 1}.png"
    Image.new("RGB", (8, 6), (220, 80 + index, 40)).save(path)
    paths.append({"path": str(path), "format": "png", "bytes": path.stat().st_size})
  return {
    "id": gen_id,
    "time": "2026-09-03T10:00:00+01:00",
    "name": "deep-between",
    "prompt": "A full prompt that must remain visible in the details panel.",
    "alias": "gdm:nb2",
    "model_id": "gemini-3.1-flash-image",
    "provider": "google",
    "n": outputs,
    "outputs": paths,
    "cost_usd_estimated": 0.101,
    "workdir": str(root),
  }


class _ImageProbe(Static):
  def __init__(self, image=None, **kwargs) -> None:
    super().__init__(**kwargs)
    self.image = image


class HistoryViewModelTests(unittest.TestCase):
  def test_flattens_each_output_into_a_selectable_image(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      entry = _entry(Path(d), outputs=2)
      items = flatten_entries([entry])

    self.assertEqual(len(items), 2)
    self.assertEqual(items[0].key, "g1:0")
    self.assertEqual(items[1].key, "g1:1")
    self.assertEqual(items[1].output_label, "2/2")
    self.assertEqual(items[0].name, "deep-between")

  def test_preview_renders_colour_half_blocks_at_requested_bounds(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "image.png"
      Image.new("RGB", (8, 6), "red").save(path)
      preview = render_preview(path, width=6, height=4)

    self.assertIn("▀", preview.plain)
    self.assertLessEqual(max(map(len, preview.plain.splitlines())), 6)
    self.assertLessEqual(len(preview.plain.splitlines()), 4)

  @patch("genimg.history_view.subprocess.run")
  @patch("genimg.history_view.sys.platform", "darwin")
  def test_macos_image_copy_sends_png_pixels_to_the_clipboard(self, run) -> None:
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "image.png"
      Image.new("RGB", (8, 6), "red").save(path)
      copy_image_to_clipboard(path)

    args = run.call_args.args[0]
    self.assertEqual(args[0], "osascript")
    self.assertIn("class PNGf", args[2])
    self.assertEqual(args[3], str(path))
    self.assertTrue(run.call_args.kwargs["check"])


class HistoryViewAppTests(unittest.IsolatedAsyncioTestCase):
  async def test_protocol_preview_receives_the_original_image_path(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "image-1.png"
      app = HistoryViewApp(
        entries=[_entry(Path(d), outputs=1)],
        skipped=0,
        preview_widget_class=_ImageProbe,
      )
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        self.assertEqual(app.query_one("#preview", _ImageProbe).image, path)

  async def test_navigation_updates_selected_output_and_details(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      app = HistoryViewApp(entries=[_entry(Path(d), outputs=2)], skipped=0)
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        self.assertEqual(app.selected_item.output_index, 0)
        await pilot.press("j")
        await pilot.pause()
        self.assertEqual(app.selected_item.output_index, 1)
        self.assertIn("image-2.png", app.details_text)
        self.assertIn("A full prompt that must remain visible", app.details_text)

  async def test_details_panel_uses_bold_colour_to_separate_metadata(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      app = HistoryViewApp(entries=[_entry(Path(d), outputs=1)], skipped=0)
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        rendered = app.query_one("#details", Static).render()

    self.assertIsInstance(rendered, Content)
    self.assertEqual(rendered.plain, app.details_text)
    styled_text = [(rendered.plain[span.start:span.end], str(span.style)) for span in rendered.spans]
    self.assertIn(("deep-between", "ansi_bright_cyan bold"), styled_text)
    self.assertIn(("time", "ansi_cyan bold"), styled_text)
    self.assertIn(("model", "ansi_cyan bold"), styled_text)
    self.assertIn(("prompt", "ansi_cyan bold"), styled_text)
    styles = " ".join(style for _, style in styled_text)
    for rainbow_colour in ("magenta", "blue", "green", "yellow", "bright_white"):
      self.assertNotIn(rainbow_colour, styles)

  async def test_open_action_targets_the_exact_selected_image(self) -> None:
    opened: list[Path] = []
    with tempfile.TemporaryDirectory() as d:
      app = HistoryViewApp(
        entries=[_entry(Path(d), outputs=2)], skipped=0, opener=opened.append,
      )
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await pilot.press("j", "o")
        await pilot.pause()

    self.assertEqual(opened, [Path(d) / "image-2.png"])

  async def test_missing_image_and_skipped_sidecars_are_visible(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      entry = _entry(Path(d), outputs=1)
      Path(entry["outputs"][0]["path"]).unlink()
      app = HistoryViewApp(entries=[entry], skipped=2)
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        self.assertIn("image not found", app.preview_text.lower())
        self.assertIn("2 unreadable sidecars", app.status_text.lower())

  async def test_reload_replaces_rows_and_narrow_mode_is_explicit(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      root = Path(d)
      loaded = [([_entry(root, gen_id="old", outputs=1)], 0)]

      def loader():
        return loaded[-1]

      app = HistoryViewApp(loader=loader)
      async with app.run_test(size=(70, 30)) as pilot:
        await pilot.pause()
        self.assertTrue(app.is_narrow)
        loaded.append(([_entry(root, gen_id="new", outputs=2)], 1))
        await pilot.press("r")
        await pilot.pause()
        self.assertEqual(len(app.items), 2)
        self.assertEqual(app.items[0].generation_id, "new")
        self.assertIn("1 unreadable sidecar", app.status_text.lower())

  async def test_help_opens_without_treating_key_labels_as_markup(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      app = HistoryViewApp(entries=[_entry(Path(d), outputs=1)], skipped=0)
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await pilot.press("?")
        await pilot.pause()
        self.assertIsInstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        self.assertNotIsInstance(app.screen, HelpScreen)

  async def test_vim_yank_shortcuts_copy_image_and_absolute_path(self) -> None:
    copied_images: list[Path] = []
    copied_paths: list[str] = []
    with tempfile.TemporaryDirectory() as d:
      path = Path(d) / "image-1.png"
      app = HistoryViewApp(
        entries=[_entry(Path(d), outputs=1)],
        skipped=0,
        image_copier=copied_images.append,
        path_copier=copied_paths.append,
      )
      async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await pilot.press("y", "i")
        await pilot.pause()
        await pilot.press("y", "p")
        await pilot.pause()

    self.assertEqual(copied_images, [path])
    self.assertEqual(copied_paths, [str(path.resolve())])


if __name__ == "__main__":
  unittest.main()
