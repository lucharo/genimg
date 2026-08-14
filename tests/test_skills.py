from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from genimg import cli


class BundledSkillTests(unittest.TestCase):
  def test_genimg_infographic_is_discoverable(self) -> None:
    sources = cli._skill_sources()

    self.assertEqual(
      set(sources),
      {"genimg", "genimg-agent-refinement", "genimg-infographic", "image-to-app"},
    )
    self.assertTrue((sources["genimg-infographic"] / "SKILL.md").is_file())
    self.assertTrue(
      (sources["genimg-infographic"] / "references" / "layouts" / "bento-grid.md").is_file()
    )
    self.assertTrue(
      (sources["genimg-infographic"] / "references" / "styles" / "technical-schematic.md").is_file()
    )
    licence = (sources["genimg-infographic"] / "LICENSE").read_text()
    self.assertIn("Copyright (c) 2026 Jim Liu", licence)
    self.assertIn("Permission is hereby granted", licence)

  def test_genimg_infographic_complete_manifest_is_in_wheel(self) -> None:
    root = Path(__file__).resolve().parents[1]
    skill = cli._skill_sources()["genimg-infographic"]
    source_files = {
      path.relative_to(skill).as_posix()
      for path in skill.rglob("*")
      if path.is_file()
    }

    with tempfile.TemporaryDirectory() as output_dir:
      result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", output_dir],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
      )
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
      wheel = next(Path(output_dir).glob("*.whl"))
      prefix = "genimg/_skills/genimg-infographic/"
      with zipfile.ZipFile(wheel) as archive:
        wheel_files = {
          name.removeprefix(prefix)
          for name in archive.namelist()
          if name.startswith(prefix) and not name.endswith("/")
        }

    self.assertEqual(wheel_files, source_files)

  def test_layout_pairings_reference_bundled_styles(self) -> None:
    skill = cli._skill_sources()["genimg-infographic"]
    style_names = {path.stem for path in (skill / "references" / "styles").glob("*.md")}
    paired_names: set[str] = set()

    for layout in (skill / "references" / "layouts").glob("*.md"):
      _, _, pairings = layout.read_text().partition("## Recommended Pairings")
      paired_names.update(re.findall(r"^- `([^`]+)`:", pairings, flags=re.MULTILINE))

    self.assertEqual(paired_names - style_names, set())

  def test_genimg_infographic_path_command(self) -> None:
    result = CliRunner().invoke(
      cli._app,
      ["skills", "path", "genimg-infographic"],
    )

    self.assertEqual(result.exit_code, 0, result.output)
    self.assertIn("skills/genimg-infographic", result.output)

  def test_port_contains_no_old_backend_contract(self) -> None:
    skill = cli._skill_sources()["genimg-infographic"]
    text = "\n".join(
      path.read_text()
      for path in skill.rglob("*.md")
    )

    self.assertNotIn("codex-imagegen", text)
    self.assertNotIn("baoyu-image-gen", text)
    self.assertNotIn("preferred_image_backend", text)
    self.assertNotIn("image_generate tool", text)
    self.assertNotIn("auth --check --json", text)
    self.assertIn("genimg auth --check", text)


if __name__ == "__main__":
  unittest.main()
