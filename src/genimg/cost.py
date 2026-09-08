"""Per-image cost estimation. Sourced from OpenAI image guide + Google Vertex pricing (Apr 2026).

These are coarse estimates — actual billing varies by tier, batch, and exact pixel count.
"""
from __future__ import annotations

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

# Google flat per-image (Gemini Image / Imagen) keyed by max-edge resolution.
# Rough public rates (Vertex pricing + cloudprice.net); refine as pricing changes.
# Keyed by the stable model id; estimate() also normalizes legacy "-preview" callers.
_GOOGLE_PER_IMAGE = {
  "gemini-3-pro-image":             {None: 0.134, "1K": 0.134, "2K": 0.134, "4K": 0.24},
  "gemini-3.1-flash-image":         {None: 0.067, "512": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
  "gemini-3.1-flash-lite-image":    {None: 0.034, "1K": 0.034, "2K": 0.05, "4K": 0.076},
  "gemini-2.5-flash-image":         {None: 0.04, "1K": 0.04, "2K": 0.13, "4K": 0.24},
  "imagen-4.0-generate-001":        {None: 0.04, "1K": 0.04, "2K": 0.04, "4K": 0.04},
  "imagen-4.0-fast-generate-001":   {None: 0.02, "1K": 0.02, "2K": 0.02, "4K": 0.02},
  "imagen-4.0-ultra-generate-001":  {None: 0.06, "1K": 0.06, "2K": 0.06, "4K": 0.06},
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
