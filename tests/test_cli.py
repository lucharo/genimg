from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from genimg import cli, metadata
from genimg.interfaces import GenerateResult


class GenerationMetadataTests(unittest.TestCase):
  def test_grid_failure_keeps_image_metadata(self) -> None:
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      out_path = root / "image.png"
      meta_dir = root / "metadata"
      grid_dir = root / "grids"

      def fake_generate(*args, **kwargs) -> GenerateResult:
        paths = [out_path.with_name("image_1.png"), out_path.with_name("image_2.png")]
        for path in paths:
          path.write_bytes(b"png")
        return GenerateResult(paths=paths, model_used="gpt-image-2")

      with (
        patch.object(metadata, "META_DIR", meta_dir),
        patch.object(metadata, "GRID_DIR", grid_dir),
        patch.object(metadata, "make_id", return_value="test-gen"),
        patch.object(cli, "run_generate", side_effect=fake_generate),
        patch.object(cli.grid_module, "render", side_effect=RuntimeError("grid failed")),
      ):
        result = runner.invoke(cli._app, ["prompt", "-m", "oai:gi2", "-n", "2", "-g", "-o", str(out_path)])

      self.assertNotEqual(result.exit_code, 0)
      meta_path = meta_dir / "test-gen.json"
      self.assertTrue(meta_path.exists())
      payload = json.loads(meta_path.read_text())
      self.assertEqual([Path(item["path"]).name for item in payload["outputs"]], ["image_1.png", "image_2.png"])
      self.assertNotIn("grid", payload)


if __name__ == "__main__":
  unittest.main()
