from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
  def test_release_please_branch_gets_explicit_exact_head_ci(self) -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()

    self.assertIn("workflow_dispatch:", ci)
    self.assertIn("actions: write", release)
    self.assertIn("--json headRefName", release)
    self.assertIn(
      'gh workflow run ci.yml --repo "$GITHUB_REPOSITORY" --ref "$branch"', release
    )

  def test_manual_release_keeps_the_green_check_gate(self) -> None:
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()

    self.assertIn('if gh pr checks "$pr"', release)
    self.assertNotIn("--admin", release)


if __name__ == "__main__":
  unittest.main()
