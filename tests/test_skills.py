from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import click
import typer
from typer.testing import CliRunner

from genimg import cli


class BundledSkillTests(unittest.TestCase):
  def test_genimg_infographic_is_discoverable(self) -> None:
    sources = cli._skill_sources()

    self.assertEqual(
      set(sources),
      {"genimg", "genimg-infographic", "image-to-app"},
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

  def test_bare_skills_prints_the_npx_install_hint(self) -> None:
    result = CliRunner().invoke(cli._app, ["skills"])

    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(
      result.output,
      "Install the bundled skills into your agent:\n"
      "  npx skills add lucharo/genimg\n"
      "Needs Node.js (for npx).\n",
    )

  def test_retired_installer_verbs_are_not_commands(self) -> None:
    """`npx skills` is the only install path (issue #5); the old verbs must not linger."""
    for verb in ("install", "update", "uninstall", "list"):
      with self.subTest(verb=verb):
        result = CliRunner().invoke(cli._app, ["skills", verb])

        self.assertEqual(result.exit_code, 2, result.output)
        self.assertIn("No such command", result.output)

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

  def test_infographic_generation_choices_are_automatic(self) -> None:
    skill = cli._skill_sources()["genimg-infographic"]
    workflow = (skill / "SKILL.md").read_text()
    setup = (skill / "references" / "config" / "first-time-setup.md").read_text()
    schema = (skill / "references" / "config" / "preferences-schema.md").read_text()

    self.assertIn("### 4. Select automatically", workflow)
    self.assertIn("Do not present a menu or ask for confirmation", workflow)
    self.assertIn("Do not run a first-time questionnaire", setup)
    self.assertIn("Preferences guide automatic selection", schema)
    self.assertIn("Automatic user/source rule", schema)
    self.assertIn("compatible saved preference", workflow)
    for legacy_phrase in (
      "### 4. Recommend and confirm",
      "confirmation gate",
      "per-generation confirmation",
      "complete its blocking setup",
      "never bypasses confirmation",
    ):
      self.assertNotIn(legacy_phrase, workflow + setup + schema)

  def test_genimg_skill_documents_multi_view_reset_recipe(self) -> None:
    workflow = " ".join(
      cli._skill_sources()["genimg"].joinpath("SKILL.md").read_text().split()
    )

    for requirement in (
      "each original camera angle as `-i`",
      "approved image as the locked appearance reference",
      "one decision per call",
      "Never feed a generated angle into the next angle",
      "reset to the originals",
      "human reject examples",
      "not a separate image model",
    ):
      self.assertIn(requirement, workflow)

  def test_genimg_skill_flag_table_lists_every_generation_option(self) -> None:
    """The skill's flag table must name every option of the hidden generate command, so an
    agent never has to run --help to discover a flag (issue #32)."""
    text = cli._skill_sources()["genimg"].joinpath("SKILL.md").read_text()
    table = text.split("## Flags (generation)", 1)[1].split("\n## ", 1)[0]
    run = typer.main.get_command(cli._app).commands["_run"]
    expected = {}
    for param in run.params:
      if not isinstance(param, click.Option) or "--help" in param.opts:
        continue
      long = next(o for o in param.opts if o.startswith("--"))
      short = next((o for o in param.opts if not o.startswith("--")), "")
      expected[long] = short
    self.assertGreater(len(expected), 15)
    rows = {}
    for line in table.splitlines():
      cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
      if len(cells) >= 2 and cells[0].startswith("--") and cells[0] != "---":
        rows[cells[0]] = cells[1]
    self.assertEqual(rows, expected)


if __name__ == "__main__":
  unittest.main()
