"""The setup wizard's closing summary names each saved profile table."""
from __future__ import annotations

from rich.console import Console

from genimg import setup


def test_profile_line_keeps_the_table_name_rich_would_eat():
  console = Console(record=True, width=120)

  console.print(setup._profile_line("google", {"provider": "google", "auth": "direct", "region": "global"}))

  assert console.export_text().strip() == "[profiles.google] google / direct  (region=global)"
