from __future__ import annotations

import base64
import http.client
import json
import os
import tempfile
import threading
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

  def test_manual_aspect_overrides_canvas_ratio(self) -> None:
    self.assertEqual(draw.pick_size("google", 1024, 1024, "4K", "16:9"), ("16:9", "4K"))

  def test_openai_snaps_resolution_to_valid_aspect_pair(self) -> None:
    self.assertEqual(draw.pick_size("openai", 1920, 1080, "1K"), ("16:9", "2K"))
    self.assertEqual(draw.pick_size("openai", 1200, 900, "4K"), ("4:3", "2K"))


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

  def test_openai_honors_manual_aspect_and_compatible_resolution(self) -> None:
    argv = self._argv(
      prompt="p", model="oai:gpt-image-2", quality="high", resolution="4K",
      aspect="16:9", w=1024, h=1024,
    )
    self.assertEqual(argv[argv.index("-a") + 1], "16:9")
    self.assertEqual(argv[argv.index("-r") + 1], "4K")

  def test_prompt_only_generation_omits_edit_input(self) -> None:
    with patch.object(draw.subprocess, "Popen", return_value=MagicMock()) as popen:
      self.studio.start_job(
        image_b64=None,
        prompt="a clean diagram of a feedback loop",
        model="gdm:nb2",
        quality="medium",
        resolution="1K",
        aspect="16:9",
        w=1024,
        h=1024,
      )
    argv = popen.call_args.args[0]
    self.assertNotIn("-i", argv)
    self.assertEqual(argv[-1], "a clean diagram of a feedback loop")
    self.assertEqual(argv[argv.index("-a") + 1], "16:9")
    self.assertEqual(list(self.studio.workdir.glob("*_in.png")), [])

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


class OriginGuardTests(unittest.TestCase):
  def test_missing_origin_allowed(self) -> None:  # curl/tests — not a CSRF vector
    self.assertTrue(draw._origin_allowed(None, "localhost:8788"))

  def test_same_origin_allowed(self) -> None:
    self.assertTrue(draw._origin_allowed("http://localhost:8788", "localhost:8788"))

  def test_cross_origin_refused(self) -> None:
    self.assertFalse(draw._origin_allowed("https://evil.example", "localhost:8788"))


class GenerateHttpTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = Path(tempfile.mkdtemp())
    self._patches = [
      patch.object(metadata, "GENIMG_HOME", self.tmp),
      patch.object(metadata, "GEN_DIR", self.tmp / "generations"),
      patch.object(draw.discovery, "load_fresh_cache", return_value=None),
      patch.object(draw.auth_google, "auth_info", return_value={"ok": True, "mode": "vertex", "hint": ""}),
      patch.object(draw.auth_openai, "auth_info", return_value={"ok": True, "mode": "azure", "hint": ""}),
    ]
    for p in self._patches:
      p.start()
      self.addCleanup(p.stop)
    self.studio = draw.Studio([], "gdm:nb2")
    self.httpd = draw._Server(("127.0.0.1", 0), draw._make_handler(self.studio))
    self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
    self.thread.start()
    self.addCleanup(self.httpd.server_close)
    self.addCleanup(self.httpd.shutdown)

  def test_prompt_only_request_starts_generation_without_image(self) -> None:
    self.studio.start_job = MagicMock(return_value="draw123")
    body = json.dumps({"prompt": "a clean diagram", "model": "gdm:nb2"})
    conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=2)
    self.addCleanup(conn.close)
    conn.request("POST", "/generate", body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    payload = json.loads(response.read())

    self.assertEqual(response.status, 200)
    self.assertEqual(payload, {"job_id": "draw123"})
    self.studio.start_job.assert_called_once_with(
      image_b64=None,
      prompt="a clean diagram",
      model="gdm:nb2",
      quality=None,
      resolution=None,
      aspect=None,
      w=1024,
      h=1024,
    )

  def test_disabled_model_is_rejected_server_side(self) -> None:
    boot = self.studio.boot_data()
    disabled = next(model for model in boot["models"] if model["alias"] == "oai:gpt-image-2")
    disabled.update(enabled=False, availability="unavailable", reason="not on this endpoint")
    studio = draw.Studio([], "gdm:nb2")
    studio.boot_data = MagicMock(return_value=boot)
    studio.start_job = MagicMock(return_value="must-not-run")
    httpd = draw._Server(("127.0.0.1", 0), draw._make_handler(studio))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    self.addCleanup(thread.join, 2)
    self.addCleanup(httpd.server_close)
    self.addCleanup(httpd.shutdown)

    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
    self.addCleanup(conn.close)
    conn.request(
      "POST", "/generate",
      body=json.dumps({"prompt": "a clean diagram", "model": "oai:gpt-image-2"}),
      headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()

    self.assertEqual(response.status, 400)
    self.assertEqual(json.loads(response.read()), {"error": "not on this endpoint"})
    studio.start_job.assert_not_called()


class HostGuardTests(unittest.TestCase):
  def test_loopback_hosts_allowed(self) -> None:
    for h in ("localhost:8788", "127.0.0.1:8788", "[::1]:8788", "localhost"):
      self.assertTrue(draw._host_allowed(h), h)

  def test_rebinding_host_and_missing_host_refused(self) -> None:  # DNS-rebinding defense
    self.assertFalse(draw._host_allowed("attacker.example:8788"))
    self.assertFalse(draw._host_allowed(None))


class BootJsonTests(unittest.TestCase):
  def test_angle_bracket_in_source_name_is_escaped(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    f = tmp / "a<b.png"
    f.write_bytes(b"x")
    with patch.object(metadata, "GENIMG_HOME", tmp), patch.object(metadata, "GEN_DIR", tmp / "gen"):
      js = draw._boot_json(draw.Studio([f], "gdm:nb2"))
    self.assertIn("a\\u003cb.png", js)
    self.assertNotIn("<", js)

  def test_boot_data_includes_first_image_prompt_starters(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    with patch.object(metadata, "GENIMG_HOME", tmp), patch.object(metadata, "GEN_DIR", tmp / "gen"):
      starters = draw.Studio([], "gdm:nb2").boot_data()["promptStarters"]
    self.assertEqual([item["label"] for item in starters], ["Create", "Diagram", "Polish"])


class StudioModelsTests(unittest.TestCase):
  def test_excludes_imagen_and_includes_editable_models(self) -> None:
    models = draw._studio_models()
    aliases = [m["alias"] for m in models]
    # Imagen is text-to-image only → it cannot support canvas iterations after the first image.
    self.assertNotIn("gdm:imagen4", aliases)
    self.assertTrue(all(not m["modelId"].startswith("imagen-") for m in models))
    # The image-editable models (incl. the ones previously missing from the hardcoded 3) are present.
    for a in ("gdm:nb2", "gdm:nbp", "gdm:nb2-lite", "oai:gpt-image-2", "oai:gpt-image-1.5"):
      self.assertIn(a, aliases)

  def test_resolution_controls_only_appear_for_models_that_support_them(self) -> None:
    models = {model["alias"]: model for model in draw._studio_models()}
    self.assertEqual(models["gdm:nb"]["resolutionOptions"], [])
    self.assertEqual(models["gdm:nb2"]["resolutionOptions"], ["1K", "2K", "4K"])
    self.assertEqual(models["oai:gpt-image-2"]["resolutionOptions"], ["1K", "2K", "4K"])
    self.assertEqual(
      models["oai:gpt-image-2"]["resolutionOptionsByAspect"]["16:9"], ["2K", "4K"])


class AvailableModelsTests(unittest.TestCase):
  AUTH_OK = {"google": {"ok": True, "mode": "vertex", "hint": ""},
             "openai": {"ok": True, "mode": "azure", "hint": ""}}

  def test_no_cache_shows_all_grouped_models_enabled_when_auth_is_ready(self) -> None:
    models = draw.available_models(None, self.AUTH_OK)
    self.assertEqual([m["alias"] for m in models], [m["alias"] for m in draw.STUDIO_MODELS])
    self.assertTrue(all(m["enabled"] for m in models))

  def test_provider_without_auth_is_kept_but_disabled_with_reason(self) -> None:
    auth = {**self.AUTH_OK, "openai": {"ok": False, "mode": "unset", "hint": "Run genimg setup"}}
    models = draw.available_models(None, auth)
    openai = [m for m in models if m["provider"] == "openai"]
    self.assertTrue(openai)
    self.assertTrue(all(not m["enabled"] for m in openai))
    self.assertTrue(all(m["reason"] == "Run genimg setup" for m in openai))

  def test_openai_missing_disabled_but_google_missing_is_unconfirmed(self) -> None:
    cache = {"probes": {
      "gdm:nb2": {"status": "missing"},            # Vertex under-reports → keep
      "oai:gpt-image-2": {"status": "listed"},     # keep
      "oai:gpt-image-1.5": {"status": "missing"},  # OpenAI list is authoritative → disable
    }}
    models = {m["alias"]: m for m in draw.available_models(cache, self.AUTH_OK)}
    self.assertTrue(models["gdm:nb2"]["enabled"])
    self.assertEqual(models["gdm:nb2"]["availability"], "unconfirmed")
    self.assertTrue(models["oai:gpt-image-2"]["enabled"])
    self.assertEqual(models["oai:gpt-image-2"]["availability"], "listed")
    self.assertFalse(models["oai:gpt-image-1.5"]["enabled"])

  def test_provider_region_failure_disables_only_affected_google_models(self) -> None:
    cache = {"probes": {"gdm:nb": {"status": "403", "detail": "permission denied"}}}
    models = {m["alias"]: m for m in draw.available_models(cache, self.AUTH_OK)}
    self.assertFalse(models["gdm:nb"]["enabled"])
    self.assertIn("permission denied", models["gdm:nb"]["reason"])
    self.assertTrue(models["gdm:nb2"]["enabled"])


class HistoryItemsTests(unittest.TestCase):
  def test_lists_images_newest_first_capped_and_url(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    with patch.object(metadata, "GENIMG_HOME", tmp), patch.object(metadata, "GEN_DIR", tmp / "generations"):
      studio = draw.Studio([], "gdm:nb2")
      for name, mt in [("old.png", 1000), ("mid.png", 2000), ("new.png", 3000)]:
        p = studio.gen_dir / name
        p.write_bytes(b"x")
        os.utime(p, (mt, mt))
      (studio.gen_dir / "notes.txt").write_text("x")  # non-image → excluded
      items = studio.history_items(limit=2)
    self.assertEqual([i["name"] for i in items], ["new.png", "mid.png"])
    self.assertEqual(items[0], {"name": "new.png", "url": "/gen/new.png", "model": None, "time": None})

  def test_special_char_filename_is_url_encoded(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    with patch.object(metadata, "GENIMG_HOME", tmp), patch.object(metadata, "GEN_DIR", tmp / "generations"):
      studio = draw.Studio([], "gdm:nb2")
      (studio.gen_dir / "a b&c.png").write_bytes(b"x")
      items = studio.history_items()
    self.assertEqual(items[0]["name"], "a b&c.png")
    self.assertEqual(items[0]["url"], "/gen/a%20b%26c.png")

  def test_enriches_from_metadata_sidecar(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    with (
      patch.object(metadata, "GENIMG_HOME", tmp),
      patch.object(metadata, "GEN_DIR", tmp / "generations"),
      patch.object(metadata, "META_DIR", tmp / "metadata"),
    ):
      studio = draw.Studio([], "gdm:nb2")
      img = studio.gen_dir / "g.png"
      img.write_bytes(b"x")
      metadata.META_DIR.mkdir(parents=True, exist_ok=True)
      (metadata.META_DIR / "id.json").write_text(
        json.dumps({"alias": "gdm:nb2", "time": "2026-07-06T12:00:00", "outputs": [{"path": str(img)}]}))
      items = studio.history_items()
    self.assertEqual(items[0], {"name": "g.png", "url": "/gen/g.png", "model": "gdm:nb2", "time": "2026-07-06T12:00:00"})

  def test_relative_output_path_resolved_against_workdir(self) -> None:
    tmp = Path(tempfile.mkdtemp())
    with (
      patch.object(metadata, "GENIMG_HOME", tmp),
      patch.object(metadata, "GEN_DIR", tmp / "generations"),
      patch.object(metadata, "META_DIR", tmp / "metadata"),
    ):
      studio = draw.Studio([], "gdm:nb2")
      (studio.gen_dir / "r.png").write_bytes(b"x")
      metadata.META_DIR.mkdir(parents=True, exist_ok=True)
      # sidecar stores a RELATIVE output path + the workdir it was generated in
      (metadata.META_DIR / "id.json").write_text(json.dumps(
        {"alias": "gdm:nbp", "time": "2026-01-01T00:00", "workdir": str(studio.gen_dir), "outputs": [{"path": "r.png"}]}))
      items = studio.history_items()
    self.assertEqual(items[0]["model"], "gdm:nbp")


class BootDataModelFilterTests(unittest.TestCase):
  def _models(self, fresh_cache) -> list[dict]:
    tmp = Path(tempfile.mkdtemp())
    with (
      patch.object(metadata, "GENIMG_HOME", tmp),
      patch.object(metadata, "GEN_DIR", tmp / "generations"),
      patch.object(draw.discovery, "load_fresh_cache", return_value=fresh_cache),
      patch.object(draw.auth_google, "auth_info", return_value={"ok": True, "mode": "vertex", "hint": ""}),
      patch.object(draw.auth_openai, "auth_info", return_value={"ok": True, "mode": "azure", "hint": ""}),
    ):
      return draw.Studio([], "gdm:nb2").boot_data()["models"]

  def test_stale_or_absent_cache_shows_all(self) -> None:
    # load_fresh_cache() returns None when stale/absent → all remain visible as unknown.
    self.assertEqual(len(self._models(None)), len(draw.STUDIO_MODELS))

  def test_fresh_cache_marks_unreachable_without_hiding_it(self) -> None:
    models = {m["alias"]: m for m in self._models(
      {"probes": {"oai:gpt-image-1.5": {"status": "missing"}}})}
    self.assertFalse(models["oai:gpt-image-1.5"]["enabled"])
    self.assertTrue(models["gdm:nb2"]["enabled"])


class DrawCommandModelTests(unittest.TestCase):
  """The studio model must support image input for iterations after the first image."""

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
