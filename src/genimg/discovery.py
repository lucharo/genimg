"""Probe registry models, cache results to ~/.cache/genimg/models.json (24h TTL)."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .interfaces import ProbeResult
from .providers import GeminiImageGen, OpenAIImageGen
from .registry import ModelSpec, all_canonical, resolve

CACHE_PATH = Path.home() / ".cache" / "genimg" / "models.json"
TTL_SECONDS = 24 * 60 * 60


def load_cache() -> dict[str, Any] | None:
  if not CACHE_PATH.exists():
    return None
  try:
    data = json.loads(CACHE_PATH.read_text())
  except (json.JSONDecodeError, OSError):
    return None
  if time.time() - data.get("timestamp", 0) > TTL_SECONDS:
    return None
  return data


def save_cache(probes: dict[str, ProbeResult]) -> None:
  CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    "timestamp": time.time(),
    "probes": {alias: p.model_dump() for alias, p in probes.items()},
  }
  CACHE_PATH.write_text(json.dumps(payload, indent=2))


def probe_all(parallel: int = 6) -> dict[str, ProbeResult]:
  """Probe every canonical entry in the registry. Returns alias → ProbeResult."""
  entries = list(all_canonical().items())
  google = GeminiImageGen()
  openai = OpenAIImageGen()

  def probe(item: tuple[str, ModelSpec]) -> tuple[str, ProbeResult]:
    alias, spec = item
    if spec.provider == "google":
      return alias, google.probe(spec.model_id, region=spec.region)
    return alias, openai.probe(spec.model_id)

  with ThreadPoolExecutor(max_workers=parallel) as ex:
    return dict(ex.map(probe, entries))


def get_or_probe(refresh: bool = False) -> tuple[dict[str, ProbeResult], float]:
  """Return (alias → ProbeResult, cache_age_seconds). Probes if cache stale or refresh=True."""
  if not refresh:
    cached = load_cache()
    if cached:
      probes = {a: ProbeResult.model_validate(p) for a, p in cached["probes"].items()}
      return probes, time.time() - cached["timestamp"]
  probes = probe_all()
  save_cache(probes)
  return probes, 0.0


