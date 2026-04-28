"""History helpers: read metadata sidecars, summarize spend."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import metadata


def recent(limit: int = 20) -> list[dict[str, Any]]:
  """Return up to `limit` most-recent metadata entries (newest first)."""
  if not metadata.META_DIR.exists():
    return []
  files = sorted(metadata.META_DIR.glob("*.json"), reverse=True)[:limit]
  out: list[dict[str, Any]] = []
  for f in files:
    try:
      out.append(json.loads(f.read_text()))
    except (json.JSONDecodeError, OSError):
      continue
  return out


def total_spent() -> tuple[float, int]:
  """Sum estimated cost across all metadata files. Returns (usd, count)."""
  if not metadata.META_DIR.exists():
    return 0.0, 0
  total = 0.0
  count = 0
  for f in metadata.META_DIR.glob("*.json"):
    try:
      data = json.loads(f.read_text())
      total += float(data.get("cost_usd_estimated", 0.0))
      count += 1
    except (json.JSONDecodeError, OSError, ValueError):
      continue
  return total, count
