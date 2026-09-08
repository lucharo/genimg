"""Model registry: aliases → canonical (provider, model_id, region, quality_rank)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal["google", "openai", "codex"]


@dataclass(frozen=True)
class ModelSpec:
  provider: Provider
  model_id: str
  region: str | None = None  # google only
  quality_rank: int = 5      # higher = better, used for auto-select


_REGISTRY: dict[str, ModelSpec | str] = {
  # A subscription backend, not a pinned image model. Opt in explicitly.
  "codex:image": ModelSpec("codex", "codex:image", quality_rank=0),
  # Google DeepMind / Gemini Image. Canonical alias is gdm:<short>; descriptive
  # nano-banana* names are kept for discoverability. Bare model ids also resolve.
  "gdm:nbp":             ModelSpec("google", "gemini-3-pro-image",             region="global", quality_rank=10),
  "gdm:nano-banana-pro": "gdm:nbp",
  "gdm:nb2":             ModelSpec("google", "gemini-3.1-flash-image",         region="global", quality_rank=8),
  "gdm:nano-banana-2":   "gdm:nb2",
  "gdm:nb2-lite":        ModelSpec("google", "gemini-3.1-flash-lite-image",    region="global", quality_rank=6),
  "gdm:nano-banana-2-lite": "gdm:nb2-lite",
  "gdm:nb":              ModelSpec("google", "gemini-2.5-flash-image",         region="us-central1", quality_rank=6),
  "gdm:nano-banana":     "gdm:nb",
  "gdm:imagen4":         ModelSpec("google", "imagen-4.0-generate-001",        region="us-central1", quality_rank=7),
  "gdm:imagen4-fast":    ModelSpec("google", "imagen-4.0-fast-generate-001",   region="us-central1", quality_rank=5),
  "gdm:imagen4-ultra":   ModelSpec("google", "imagen-4.0-ultra-generate-001",  region="us-central1", quality_rank=8),

  # OpenAI / Azure OpenAI.
  # Availability varies by account and Azure deployment — run `genimg models` to see
  # what your credentials can actually reach. Some ids (e.g. gpt-image-1.5) may be
  # OpenAI-direct only and absent from a given Azure resource.
  "oai:gpt-image-2.5-sunburst": ModelSpec("openai", "gpt-image-2.5-sunburst", quality_rank=10),
  "oai:gi2.5":            "oai:gpt-image-2.5-sunburst",
  "oai:gpt-image-2.5-flare": ModelSpec("openai", "gpt-image-2.5-flare", quality_rank=9),
  "oai:gi2.5-flare":      "oai:gpt-image-2.5-flare",
  "oai:gpt-image-2":      ModelSpec("openai", "gpt-image-2",      quality_rank=9),
  "oai:gi2":              "oai:gpt-image-2",
  "oai:gpt-image-1.5":    ModelSpec("openai", "gpt-image-1.5",    quality_rank=7),
  "oai:gi1.5":            "oai:gpt-image-1.5",
  "oai:gpt-image-1":      ModelSpec("openai", "gpt-image-1",      quality_rank=5),
  "oai:gi1":              "oai:gpt-image-1",
  "oai:gpt-image-1-mini": ModelSpec("openai", "gpt-image-1-mini", quality_rank=4),
  "oai:gi1-mini":         "oai:gpt-image-1-mini",
}

def _infer_spec(model_id: str) -> ModelSpec | None:
  """Infer a spec for a well-formed but unregistered model id from its shape.

  Provider dispatch is structural — the id prefix already tells us the provider and code
  path — so a new same-signature model works via `-m <full-id>` with no code change. The
  registry stays a pure curation layer (short aliases, quality_rank, region pins);
  inferred specs get quality_rank=0 (never auto-ranked) and a sane default region.

  Only the gpt-image request shape is inferred for OpenAI. `dall-e-*` is intentionally
  excluded: the OpenAI provider always sends gpt-image-style size/quality params that
  DALL-E rejects, so inferring it would resolve then fail at generation.
  """
  mid = model_id.lower()
  if mid.startswith("gpt-image"):
    return ModelSpec("openai", model_id, region=None, quality_rank=0)
  if mid.startswith("imagen-"):
    return ModelSpec("google", model_id, region="us-central1", quality_rank=0)
  if mid.startswith("gemini-") and "image" in mid:
    return ModelSpec("google", model_id, region="global", quality_rank=0)
  return None


def resolve(name: str) -> tuple[str, ModelSpec]:
  """Resolve an alias, a registered bare model id, or an unregistered same-signature id.

  Three tiers, tried in order:
    1. alias chain in the registry (gdm:nb2 → …)
    2. reverse lookup of a registered bare model id (e.g. 'gpt-image-2')
    3. structural inference for a well-formed but unregistered id (see _infer_spec) —
       lets a brand-new same-shape model work via its full id without a registry edit.
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
  inferred = _infer_spec(name)
  if inferred is not None:
    return name, inferred
  raise ValueError(
    f"unknown model {name!r}. Run `genimg models` to see aliases, or pass a full provider "
    f"model id (gpt-image-*, imagen-*, or gemini-*-image)."
  )


def all_canonical() -> dict[str, ModelSpec]:
  """Return alias → ModelSpec for every direct (non-aliased) entry."""
  return {k: v for k, v in _REGISTRY.items() if isinstance(v, ModelSpec)}


def aliases_for(canonical_alias: str) -> list[str]:
  """All aliases that resolve to the same canonical alias."""
  return sorted(k for k, v in _REGISTRY.items() if isinstance(v, str) and v == canonical_alias)
