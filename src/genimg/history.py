"""History helpers: read metadata sidecars, summarize spend."""
from __future__ import annotations

import json
from typing import Any

from . import cost, metadata


def load(limit: int | None = None) -> tuple[list[dict[str, Any]], int]:
  """Return normalised metadata entries (newest first) and skipped-file count."""
  if not metadata.META_DIR.exists():
    return [], 0
  files = sorted(metadata.META_DIR.glob("*.json"), reverse=True)
  out: list[dict[str, Any]] = []
  skipped = 0
  for f in files:
    if limit is not None and len(out) >= limit:
      break
    try:
      out.append(metadata.normalize_paths(json.loads(f.read_text())))
    except (json.JSONDecodeError, OSError, TypeError, ValueError, KeyError):
      skipped += 1
      continue
  return out, skipped


def recent(limit: int = 20) -> list[dict[str, Any]]:
  """Return up to `limit` most-recent valid metadata entries (newest first)."""
  return load(limit=limit)[0]


def total_spent() -> tuple[float, int]:
  """Sum known estimates. Returns (usd, priced generation count); excludes unknowns."""
  if not metadata.META_DIR.exists():
    return 0.0, 0
  total = 0.0
  count = 0
  for f in metadata.META_DIR.glob("*.json"):
    try:
      data = json.loads(f.read_text())
      if cost.billing_label(data) != "api":
        continue
      value = data.get("cost_usd_estimated")
      if value is None:
        continue
      total += float(value)
      count += 1
    except (json.JSONDecodeError, OSError, ValueError):
      continue
  return total, count
