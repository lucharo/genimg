"""Probe registry models, cache results to ~/.cache/genimg/models.json."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .interfaces import ProbeResult
from .registry import ModelSpec, all_canonical

CACHE_PATH = Path.home() / ".cache" / "genimg" / "models.json"
CACHE_REFRESH_INTERVAL_SECONDS = 5 * 24 * 60 * 60
MAX_PROBE_PARALLELISM = 16


def load_cache() -> dict[str, Any] | None:
  if not CACHE_PATH.exists():
    return None
  try:
    data = json.loads(CACHE_PATH.read_text())
  except (json.JSONDecodeError, OSError):
    return None
  if not isinstance(data, dict) or not isinstance(data.get("probes"), dict):
    return None
  return data


def cache_age_seconds(cached: dict[str, Any]) -> float:
  return time.time() - float(cached.get("timestamp", 0))


def is_cache_stale(cached: dict[str, Any]) -> bool:
  return cache_age_seconds(cached) > CACHE_REFRESH_INTERVAL_SECONDS


def load_fresh_cache() -> dict[str, Any] | None:
  cached = load_cache()
  if cached and not is_cache_stale(cached):
    return cached
  return None


def save_cache(probes: dict[str, ProbeResult]) -> None:
  CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    "timestamp": time.time(),
    "probes": {alias: p.model_dump() for alias, p in probes.items()},
  }
  CACHE_PATH.write_text(json.dumps(payload, indent=2))


def probe_all(parallel: int | None = None) -> dict[str, ProbeResult]:
  """Check registry entries against free provider model-list endpoints."""
  entries = list(all_canonical().items())
  if not entries:
    return {}
  groups = _probe_groups(entries)

  requested_parallelism = parallel or MAX_PROBE_PARALLELISM
  worker_count = min(len(groups), max(1, requested_parallelism))
  with ThreadPoolExecutor(max_workers=worker_count) as ex:
    results = ex.map(lambda group: group(), groups)
  probes: dict[str, ProbeResult] = {}
  for group_result in results:
    probes.update(group_result)
  return probes


def _probe_groups(entries: list[tuple[str, ModelSpec]]):
  """One probe job per provider; each provider batches its own entries (e.g. per region)."""
  from .providers import get
  by_provider: dict[str, list[tuple[str, ModelSpec]]] = {}
  for alias, spec in entries:
    by_provider.setdefault(spec.provider, []).append((alias, spec))
  groups = []
  for name, cohort in by_provider.items():
    provider = get(name)  # raises ValueError for an unregistered provider
    groups.append(lambda provider=provider, cohort=cohort: provider.probe_listed(cohort))
  return groups


def get_or_probe(refresh: bool = False, cached: dict[str, Any] | None = None) -> tuple[dict[str, ProbeResult], float]:
  """Return (alias → ProbeResult, cache_age_seconds). Probes if cache stale or refresh=True."""
  if not refresh:
    cached = cached if cached is not None else load_cache()
    if cached and not is_cache_stale(cached):
      probes = {a: ProbeResult.model_validate(p) for a, p in cached["probes"].items()}
      return probes, cache_age_seconds(cached)
  probes = probe_all()
  save_cache(probes)
  return probes, 0.0
