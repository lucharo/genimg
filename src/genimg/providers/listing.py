"""Shared helpers for models.list()-based availability probes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..interfaces import ProbeResult


def listed_model_ids(models: Iterable[Any]) -> set[str]:
  ids: set[str] = set()
  for model in models:
    for attr in ("id", "name", "model", "display_name"):
      value = model.get(attr) if isinstance(model, dict) else getattr(model, attr, None)
      if isinstance(value, str) and value:
        ids.add(value)
        ids.add(value.rsplit("/", 1)[-1])
  return ids


def results_from_model_ids(entries: list[tuple[str, Any]], listed_ids: set[str]) -> dict[str, ProbeResult]:
  return {
    alias: ProbeResult(
      model=spec.model_id,
      status="listed" if spec.model_id in listed_ids else "missing",
      detail="" if spec.model_id in listed_ids else "not enumerated by the provider list endpoint (may still be usable)",
    )
    for alias, spec in entries
  }


def error_results(entries: list[tuple[str, Any]], status: str, detail: str) -> dict[str, ProbeResult]:
  return {alias: ProbeResult(model=spec.model_id, status=status, detail=detail[:200]) for alias, spec in entries}
