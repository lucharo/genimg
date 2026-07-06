from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from genimg import cli, draw, metadata

_IMG_DATAURL = "data:image/png;base64," + base64.b64encode(b"not-a-real-png").decode()


class DiscoverImagesTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = Path(tempfile.mkdtemp())
    (self.tmp / "a.png").write_bytes(b"x")
    (self.tmp / "b.JPG").write_bytes(b"x")   # case-insensitive ext
    (self.tmp / "notes.txt").write_bytes(b"x")

  def test_directory_globs_images_only_sorted(self) -> None:
    got = [p.name for p in draw.discover_images([self.tmp])]
    self.assertEqual(got, ["a.png", "b.JPG"])

  def test_file_arg_and_dedup_against_dir(self) -> None:
    # Passing the dir AND a file already inside it must not duplicate that file.
    got = [p.name for p in draw.discover_images([self.tmp, self.tmp / "a.png"])]
    self.assertEqual(got, ["a.png", "b.JPG"])

  def test_non_image_and_missing_paths_yield_empty(self) -> None:
    self.assertEqual(draw.discover_images([self.tmp / "notes.txt", self.tmp / "gone.png"]), [])


class PickSizeTests(unittest.TestCase):
  def test_openai_wide_forces_2k(self) -> None:
    self.assertEqual(draw.pick_size("openai", 1920, 1080, None), ("16:9", "2K"))

  def test_openai_square_stays_1k(self) -> None:
    self.assertEqual(draw.pick_size("openai", 1024, 1024, None), ("1:1", "1K"))

  def test_gemini_passes_image_size_through(self) -> None:
    self.assertEqual(draw.pick_size("google", 1000, 1400, "2K"), ("3:4", "2K"))


class StartJobArgvTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = Path(tempfile.mkdtemp())
    self._patches = [
      patch.object(metadata, "GENIMG_HOME", self.tmp),
      patch.object(metadata, "GEN_DIR", self.tmp / "generations"),
      patch.object(draw, "_genimg_cmd", return_value=["genimg"]),
    ]
    for p in self._patches:
      p.start()
      self.addCleanup(p.stop)
    self.studio = draw.Studio([], default_model="gdm:nb2")

  def _argv(self, **kw) -> list[str]:
    with patch.object(draw.subprocess, "Popen", return_value=MagicMock()) as popen:
      self.studio.start_job(image_b64=_IMG_DATAURL, **kw)
    return popen.call_args.args[0]

  def test_gemini_uses_resolution_not_quality(self) -> None:
    argv = self._argv(prompt="p", model="gdm:nb2", quality="medium", resolution="2K", w=1000, h=1000)
    self.assertIn("-r", argv)
    self.assertEqual(argv[argv.index("-r") + 1], "2K")
    self.assertNotIn("-q", argv)
    self.assertEqual(argv[argv.index("-m") + 1], "gdm:nb2")
    self.assertIn("-i", argv)
    self.assertIn("-a", argv)

  def test_openai_uses_quality(self) -> None:
    argv = self._argv(prompt="p", model="oai:gpt-image-2", quality="high", resolution="1K", w=1024, h=1024)
    self.assertIn("-q", argv)
    self.assertEqual(argv[argv.index("-q") + 1], "high")

  def test_leading_dash_prompt_passed_after_double_dash(self) -> None:
    # The default prompt starts with "-"; it must be routed through `_run … -- <prompt>` so
    # click parses it as a positional, not an unknown option.
    argv = self._argv(prompt="- edit marks", model="gdm:nb2", quality="medium", resolution="1K", w=1000, h=1000)
    self.assertEqual(argv[1], "_run")
    self.assertEqual(argv[-1], "- edit marks")
    self.assertEqual(argv.index("--"), len(argv) - 2)  # prompt is the sole token after --


class StatusTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = Path(tempfile.mkdtemp())
    for p in (patch.object(metadata, "GENIMG_HOME", self.tmp),
              patch.object(metadata, "GEN_DIR", self.tmp / "generations")):
      p.start()
      self.addCleanup(p.stop)
    self.studio = draw.Studio([], default_model="gdm:nb2")

  def _job(self, rc, *, out_exists: bool, log_text: str = "") -> str:
    proc = MagicMock()
    proc.poll.return_value = rc
    out = self.studio.gen_dir / "draw_x.png"
    if out_exists:
      out.write_bytes(b"png")
    log = self.studio.workdir / "x.log"
    log.write_text(log_text)
    with patch.object(draw.time, "time", return_value=1000.0):
      self.studio.jobs["x"] = draw._Job("x", "gdm:nb2", proc, out, log)
    return "x"

  def test_unknown_job(self) -> None:
    self.assertEqual(self.studio.status("nope"), {"status": "unknown"})

  def test_running_reports_elapsed(self) -> None:
    self._job(None, out_exists=False)
    with patch.object(draw.time, "time", return_value=1000.0):
      self.assertEqual(self.studio.status("x"), {"status": "running", "elapsed": 0.0})

  def test_done_returns_result_url(self) -> None:
    self._job(0, out_exists=True)
    with patch.object(draw.time, "time", return_value=1000.0):
      self.assertEqual(
        self.studio.status("x"),
        {"status": "done", "elapsed": 0.0, "resultUrl": "/gen/draw_x.png?t=1000", "fileName": "draw_x.png"},
      )

  def test_nonzero_exit_is_error_with_log_tail(self) -> None:
    self._job(2, out_exists=False, log_text="boom: safety filter")
    self.assertEqual(self.studio.status("x"), {"status": "error", "error": "boom: safety filter"})


class SafeNameTests(unittest.TestCase):
  def test_path_traversal_is_stripped_to_basename(self) -> None:
    self.assertEqual(draw._safe_name("../../etc/passwd"), "passwd")


class BootJsonTests(unittest.TestCase):
  def test_angle_bracket_in_source_name_is_escaped(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    f = tmp / "a<b.png"
    f.write_bytes(b"x")
    with patch.object(metadata, "GENIMG_HOME", tmp), patch.object(metadata, "GEN_DIR", tmp / "gen"):
      js = draw._boot_json(draw.Studio([f], "gdm:nb2"))
    self.assertIn("a\\u003cb.png", js)
    self.assertNotIn("<", js)


class DrawCommandModelTests(unittest.TestCase):
  """The studio always sends -i, so the initial model must be an image-capable studio model."""

  def _serve_model(self, args: list[str], default_cfg: str | None) -> str:
    captured: dict[str, str] = {}

    def fake_serve(sources, *, port, model, open_browser):
      captured["model"] = model

    with (
      patch.object(draw, "serve", side_effect=fake_serve),
      patch.object(cli.config, "get_default_model", return_value=default_cfg),
    ):
      CliRunner().invoke(cli._app, ["draw", "--no-open", *args])
    return captured["model"]

  def test_imagen_default_falls_back_to_nb2(self) -> None:
    self.assertEqual(self._serve_model(["-m", "gdm:imagen4"], None), "gdm:nb2")

  def test_alias_is_canonicalized_to_studio_model(self) -> None:
    self.assertEqual(self._serve_model(["-m", "oai:gi2"], None), "oai:gpt-image-2")

  def test_no_model_uses_config_default_when_supported(self) -> None:
    self.assertEqual(self._serve_model([], "gdm:nbp"), "gdm:nbp")


if __name__ == "__main__":
  unittest.main()
