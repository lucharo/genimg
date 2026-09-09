from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from genimg import cli, history, metadata


class HistoryLoadingTests(unittest.TestCase):
  def test_load_backfills_past_corrupt_sidecars_and_normalises_paths(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      root = Path(d)
      meta_dir = root / "metadata"
      workdir = root / "work"
      meta_dir.mkdir()
      workdir.mkdir()

      (meta_dir / "20260103_bad.json").write_text("{")
      (meta_dir / "20260102_b.json").write_text(json.dumps({
        "id": "b", "time": "2026-01-02T00:00:00+00:00", "workdir": str(workdir),
        "input": "input.png", "refs": ["ref.png"],
        "outputs": [{"path": "b.png"}], "grid": {"path": "b.html"},
      }))
      (meta_dir / "20260101_a.json").write_text(json.dumps({
        "id": "a", "time": "2026-01-01T00:00:00+00:00", "workdir": str(workdir),
        "outputs": [{"path": "a.png"}],
      }))

      with patch.object(metadata, "META_DIR", meta_dir):
        entries, skipped = history.load(limit=2)

      self.assertEqual([entry["id"] for entry in entries], ["b", "a"])
      self.assertEqual(skipped, 1)
      self.assertEqual(entries[0]["workdir"], str(workdir.resolve()))
      self.assertEqual(entries[0]["input"], str((workdir / "input.png").resolve()))
      self.assertEqual(entries[0]["refs"], [str((workdir / "ref.png").resolve())])
      self.assertEqual(entries[0]["outputs"][0]["path"], str((workdir / "b.png").resolve()))
      self.assertEqual(entries[0]["grid"]["path"], str((workdir / "b.html").resolve()))

  def test_load_skips_relative_paths_without_a_recorded_workdir(self) -> None:
    with tempfile.TemporaryDirectory() as d:
      meta_dir = Path(d)
      (meta_dir / "20260101_bad.json").write_text(json.dumps({
        "id": "bad", "outputs": [{"path": "unknown.png"}],
      }))

      with patch.object(metadata, "META_DIR", meta_dir):
        entries, skipped = history.load()

      self.assertEqual(entries, [])
      self.assertEqual(skipped, 1)


class HistoryCliTests(unittest.TestCase):
  def setUp(self) -> None:
    self.runner = CliRunner()
    self.entry = {
      "id": "20260903_example",
      "time": "2026-09-03T10:00:00+01:00",
      "name": "deep-between",
      "prompt": "A prompt long enough to prove the history table shows more than fifty characters without losing the useful ending.",
      "alias": "gdm:nb2",
      "model_id": "gemini-3.1-flash-image",
      "n": 3,
      "outputs": [
        {"path": "/tmp/one.png"},
        {"path": "/tmp/two.png"},
      ],
      "cost_usd_estimated": 0.101,
    }

  def test_static_history_shows_name_expanded_model_and_view_hint(self) -> None:
    with patch.object(history, "load", return_value=([self.entry], 0)):
      result = self.runner.invoke(cli._app, ["history"], terminal_width=180)

    self.assertEqual(result.exit_code, 0, result.output)
    plain = " ".join(result.output.split())
    self.assertIn("deep-between", plain)
    self.assertIn("gdm:nb2", plain)
    self.assertIn("gemini-3.", plain)
    self.assertIn("1-flash-i", plain)
    self.assertIn("without", plain)
    self.assertIn("2/3", plain)
    self.assertIn("Interactive browser: genimg history view", plain)

  def test_history_json_remains_a_bare_array_without_human_hint(self) -> None:
    with patch.object(history, "load", return_value=([self.entry], 0)):
      result = self.runner.invoke(cli._app, ["history", "--json"])

    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(json.loads(result.output), [self.entry])
    self.assertNotIn("Interactive browser", result.output)

  def test_history_summary_and_cost_still_work(self) -> None:
    with patch.object(history, "total_spent", return_value=(1.25, 5)):
      summary = self.runner.invoke(cli._app, ["history", "--summary"])
      cost = self.runner.invoke(cli._app, ["cost", "--json"])

    self.assertEqual(summary.exit_code, 0, summary.output)
    self.assertIn("$1.2500 across 5 generation(s)", " ".join(summary.output.split()))
    self.assertEqual(cost.exit_code, 0, cost.output)
    self.assertEqual(json.loads(cost.output), {"total_usd": 1.25, "generations": 5})

  def test_history_reports_skipped_sidecars(self) -> None:
    with patch.object(history, "load", return_value=([self.entry], 2)):
      result = self.runner.invoke(cli._app, ["history"])

    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIn("2 unreadable metadata sidecars skipped", " ".join(result.output.split()))

  def test_history_view_dispatches_to_the_tui(self) -> None:
    with patch("genimg.history_view.run") as run:
      result = self.runner.invoke(cli._app, ["history", "view"])

    self.assertEqual(result.exit_code, 0, result.output)
    run.assert_called_once_with()

  def test_history_add_replaces_root_record_and_keeps_view(self) -> None:
    import typer.main
    command = typer.main.get_command(cli._app)
    self.assertNotIn("record", command.commands)
    self.assertEqual(set(command.commands["history"].commands), {"add", "view"})


if __name__ == "__main__":
  unittest.main()
