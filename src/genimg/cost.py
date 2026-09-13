"""Per-image cost estimation. Sourced from OpenAI image guide + Google Vertex pricing (Apr 2026).

These are coarse estimates — actual billing varies by tier, batch, and exact pixel count.
"""
from __future__ import annotations

from typing import Any

# OpenAI gpt-image-2 / 1.5 / 1: per 1024x1024 image, by quality.
# https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
_OPENAI_BASE_PER_IMAGE = {
  # GPT Image 2.5 has the same token rates as 2, but different token consumption.
  # No per-image row until documented; never copy GPT Image 2's estimates.
  # https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst
  "gpt-image-2":      {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053},
  "gpt-image-1.5":    {"low": 0.009, "medium": 0.034, "high": 0.133, "auto": 0.034},
  "gpt-image-1":      {"low": 0.011, "medium": 0.042, "high": 0.167, "auto": 0.042},
  "gpt-image-1-mini": {"low": 0.004, "medium": 0.015, "high": 0.060, "auto": 0.015},
}

# Resolution scaling for OpenAI: rough multipliers (2K ≈ 2x, 4K ≈ 4x token-metered)
_OPENAI_RESOLUTION_MULT = {None: 1.0, "1K": 1.0, "2K": 2.5, "4K": 6.0}

# Google flat per-image (Gemini Image) keyed by max-edge resolution.
# Rough public rates (Vertex pricing + cloudprice.net); refine as pricing changes.
# Keyed by the stable model id; estimate() also normalizes legacy "-preview" callers.
_GOOGLE_PER_IMAGE = {
  "gemini-3-pro-image":             {None: 0.134, "1K": 0.134, "2K": 0.134, "4K": 0.24},
  "gemini-3.1-flash-image":         {None: 0.067, "512": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
  "gemini-3.1-flash-lite-image":    {None: 0.034, "1K": 0.034, "2K": 0.05, "4K": 0.076},
  "gemini-2.5-flash-image":         {None: 0.04, "1K": 0.04, "2K": 0.13, "4K": 0.24},
}


def estimate(*, provider: str, model_id: str, n: int = 1,
             quality: str | None = None, resolution: str | None = None) -> float | None:
  """Return rough USD cost for `n` images, or None when no estimate is available."""
  if provider == "openai":
    base = _OPENAI_BASE_PER_IMAGE.get(model_id, {}).get(quality or "medium")
    if base is None:
      return None
    return n * base * _OPENAI_RESOLUTION_MULT.get(resolution, 1.0)
  if provider == "google":
    # Normalize legacy preview ids so saved metadata keeps pricing identically.
    key = model_id[: -len("-preview")] if model_id.endswith("-preview") else model_id
    table = _GOOGLE_PER_IMAGE.get(key)
    if not table:
      return None
    return n * table.get(resolution, table[None])
  return None


def format_usd(value: float | None) -> str:
  return "unknown" if value is None else f"${value:.4f}"


def api_equivalent(*, provider: str, model_id: str, output: dict[str, Any],
                   quality: str | None = None, resolution: str | None = None) -> dict[str, Any]:
  """Output-only comparison, separate from billing. Native settings are unreported."""
  from .provenance import generators

  if provider != "codex":
    value = estimate(provider=provider, model_id=model_id, quality=quality, resolution=resolution)
    return {"model_id": model_id, "usd_min": value, "usd_max": value,
            "basis": "requested_model_and_settings", "assumptions": "Coarse output-image estimate; excludes input tokens."}

  # C2PA identifies a generator version, not an API deployment. Only map known
  # unambiguous versions, and retain this inference separately from the claim.
  agents = generators(output)
  versions = {a.get("version") for a in agents if a.get("name") == "gpt-image"}
  known = {"1.0": "gpt-image-1", "1.5": "gpt-image-1.5", "2.0": "gpt-image-2"}
  inferred = known.get(next(iter(versions))) if len(versions) == 1 else None
  result = {"model_id": inferred, "usd_min": None, "usd_max": None,
            "basis": "reported_c2pa_generator",
            "assumptions": "API model inferred from unverified C2PA; quality unknown. Low-to-high reference prices scaled linearly by pixel area; excludes input tokens, not a billing quote."}
  dimensions = output.get("dimensions", {})
  if inferred and dimensions.get("width") and dimensions.get("height"):
    scale = dimensions["width"] * dimensions["height"] / 1024**2
    table = _OPENAI_BASE_PER_IMAGE[inferred]
    result.update(usd_min=round(table["low"] * scale, 6), usd_max=round(table["high"] * scale, 6))
  return result


def sum_equivalents(values: list[dict[str, Any]]) -> dict[str, Any]:
  priced = [v for v in values if v.get("usd_min") is not None and v.get("usd_max") is not None]
  complete = bool(values) and len(priced) == len(values)
  return {"usd_min": round(sum(v["usd_min"] for v in priced), 6) if complete else None,
          "usd_max": round(sum(v["usd_max"] for v in priced), 6) if complete else None,
          "priced_images": len(priced), "images": len(values)}


def format_equivalent(value: dict[str, Any] | None) -> str:
  if not value or value.get("usd_min") is None or value.get("usd_max") is None:
    return "unknown"
  lower, upper = value["usd_min"], value["usd_max"]
  return format_usd(lower) if lower == upper else f"{format_usd(lower)}–{format_usd(upper)}"


def billing_label(meta: dict[str, Any]) -> str:
  return meta.get("billing") or ("subscription" if meta.get("provider") == "codex" else "api")
