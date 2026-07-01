"""Probe registry models, cache results to ~/.cache/genimg/models.json."""
from __future__ import annotations

import json
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from google.genai.errors import ClientError, ServerError
from openai import APIStatusError, AuthenticationError

from .auth import google as auth_google
from .auth import openai as auth_openai
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
  google_entries_by_region: dict[str, list[tuple[str, ModelSpec]]] = {}
  openai_entries: list[tuple[str, ModelSpec]] = []
  for alias, spec in entries:
    if spec.provider == "google":
      google_entries_by_region.setdefault(spec.region or "global", []).append((alias, spec))
    elif spec.provider == "openai":
      openai_entries.append((alias, spec))
    else:
      raise ValueError(f"unknown provider for {alias}: {spec.provider}")

  groups = []
  if openai_entries:
    groups.append(lambda entries=openai_entries: _probe_openai_from_model_list(entries))
  for region, region_entries in google_entries_by_region.items():
    groups.append(lambda region=region, entries=region_entries: _probe_google_from_model_list(region, entries))
  return groups


def _probe_openai_from_model_list(entries: list[tuple[str, ModelSpec]]) -> dict[str, ProbeResult]:
  try:
    client = auth_openai.get_client()
    listed_ids = _listed_model_ids(client.models.list())
    return _results_from_model_ids(entries, listed_ids)
  except AuthenticationError as e:
    return _error_results(entries, "auth", str(e))
  except APIStatusError as e:
    status = "403" if e.status_code == 403 else ("404" if e.status_code == 404 else "error")
    return _error_results(entries, status, f"{e.status_code}: {str(e)}")
  except Exception as e:
    return _error_results(entries, "error", f"{type(e).__name__}: {e}")


def _probe_google_from_model_list(region: str, entries: list[tuple[str, ModelSpec]]) -> dict[str, ProbeResult]:
  try:
    client = auth_google.get_client(region=region)
    listed_ids = _listed_model_ids(client.models.list())
    return _results_from_model_ids(entries, listed_ids)
  except ClientError as e:
    code = getattr(e, "code", None)
    status = str(code) if code in (403, 404) else "error"
    return _error_results(entries, status, f"{code}: {str(e)}")
  except ServerError as e:
    return _error_results(entries, "error", str(e))
  except Exception as e:
    return _error_results(entries, "error", f"{type(e).__name__}: {e}")


def _listed_model_ids(models: Iterable[Any]) -> set[str]:
  ids: set[str] = set()
  for model in models:
    for attr in ("id", "name", "model", "display_name"):
      value = _model_attr(model, attr)
      if isinstance(value, str) and value:
        ids.add(value)
        ids.add(value.rsplit("/", 1)[-1])
  return ids


def _model_attr(model: Any, attr: str) -> Any:
  if isinstance(model, dict):
    return model.get(attr)
  return getattr(model, attr, None)


def _results_from_model_ids(entries: list[tuple[str, ModelSpec]], listed_ids: set[str]) -> dict[str, ProbeResult]:
  return {
    alias: ProbeResult(
      model=spec.model_id,
      status="listed" if spec.model_id in listed_ids else "missing",
      detail="" if spec.model_id in listed_ids else "not listed by provider model endpoint",
    )
    for alias, spec in entries
  }


def _error_results(entries: list[tuple[str, ModelSpec]], status: str, detail: str) -> dict[str, ProbeResult]:
  return {
    alias: ProbeResult(model=spec.model_id, status=status, detail=detail[:200])
    for alias, spec in entries
  }


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
