"""Model registry: aliases → canonical (provider, model_id, region, quality_rank)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal["google", "openai"]


@dataclass(frozen=True)
class ModelSpec:
  provider: Provider
  model_id: str
  region: str | None = None  # google only
  quality_rank: int = 5      # higher = better, used for auto-select


_REGISTRY: dict[str, ModelSpec | str] = {
  # Google DeepMind / Gemini Image
  "gdm:nbp":             ModelSpec("google", "gemini-3-pro-image-preview",     region="global", quality_rank=10),
  "gdm:nano-banana-pro": "gdm:nbp",
  "google:nbp":          "gdm:nbp",
  "gdm:nb2":             ModelSpec("google", "gemini-3.1-flash-image-preview", region="global", quality_rank=8),
  "gdm:nano-banana-2":   "gdm:nb2",
  "google:nb2":          "gdm:nb2",
  "gdm:nb":              ModelSpec("google", "gemini-2.5-flash-image",         region="us-central1", quality_rank=6),
  "gdm:nano-banana":     "gdm:nb",
  "google:nb":           "gdm:nb",
  "gdm:imagen4":         ModelSpec("google", "imagen-4.0-generate-001",        region="us-central1", quality_rank=7),
  "google:imagen4":      "gdm:imagen4",
  "gdm:imagen4-fast":    ModelSpec("google", "imagen-4.0-fast-generate-001",   region="us-central1", quality_rank=5),
  "google:imagen4-fast": "gdm:imagen4-fast",
  "gdm:imagen4-ultra":   ModelSpec("google", "imagen-4.0-ultra-generate-001",  region="us-central1", quality_rank=8),
  "google:imagen4-ultra": "gdm:imagen4-ultra",

  # OpenAI / Azure OpenAI
  # Verified from developers.openai.com/cookbook (Apr 2026 prompting guide) +
  # OpenAI deprecations table. Azure example-azure-resource currently exposes
  # gpt-image-2, gpt-image-1, gpt-image-1-mini (gpt-image-1.5 is OpenAI-direct only).
  "oai:gpt-image-2":      ModelSpec("openai", "gpt-image-2",      quality_rank=9),
  "oai:gi2":              "oai:gpt-image-2",
  "openai:gi2":           "oai:gpt-image-2",
  "openai:gpt-image-2":   "oai:gpt-image-2",
  "oai:gpt-image-1.5":    ModelSpec("openai", "gpt-image-1.5",    quality_rank=7),
  "oai:gi1.5":            "oai:gpt-image-1.5",
  "oai:gpt-image-1":      ModelSpec("openai", "gpt-image-1",      quality_rank=5),
  "oai:gi1":              "oai:gpt-image-1",
  "oai:gpt-image-1-mini": ModelSpec("openai", "gpt-image-1-mini", quality_rank=4),
  "oai:gi1-mini":         "oai:gpt-image-1-mini",
  "oai:gi1m":             "oai:gpt-image-1-mini",
}

DEFAULT = "gdm:nb2"


def resolve(name: str) -> tuple[str, ModelSpec]:
  """Resolve alias chain or bare model id to (canonical_alias, spec).

  Accepts bare model IDs like 'gpt-image-2' or 'gemini-3.1-flash-image-preview'
  by reverse-looking-up in the registry.
  """
  seen: set[str] = set()
  key = name
  while key in _REGISTRY:
    if key in seen:
      raise ValueError(f"alias cycle for {name!r}")
    seen.add(key)
    val = _REGISTRY[key]
    if isinstance(val, ModelSpec):
      return key, val
    key = val
  for alias, val in _REGISTRY.items():
    if isinstance(val, ModelSpec) and val.model_id == name:
      return alias, val
  raise ValueError(f"unknown model {name!r}. Run `genimg models` to see available aliases.")


def all_canonical() -> dict[str, ModelSpec]:
  """Return alias → ModelSpec for every direct (non-aliased) entry."""
  return {k: v for k, v in _REGISTRY.items() if isinstance(v, ModelSpec)}


def aliases_for(canonical_alias: str) -> list[str]:
  """All aliases that resolve to the same canonical alias."""
  return sorted(k for k, v in _REGISTRY.items() if isinstance(v, str) and v == canonical_alias)
