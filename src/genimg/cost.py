"""Per-image cost estimation. Sourced from OpenAI image guide + Google Vertex pricing (Apr 2026).

These are coarse estimates — actual billing varies by tier, batch, and exact pixel count.
"""
from __future__ import annotations

# OpenAI gpt-image-2 / 1.5 / 1: per 1024x1024 image, by quality.
# https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
_OPENAI_BASE_PER_IMAGE = {
  "gpt-image-2":      {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053},
  "gpt-image-1.5":    {"low": 0.009, "medium": 0.034, "high": 0.133, "auto": 0.034},
  "gpt-image-1":      {"low": 0.011, "medium": 0.042, "high": 0.167, "auto": 0.042},
  "gpt-image-1-mini": {"low": 0.004, "medium": 0.015, "high": 0.060, "auto": 0.015},
}

# Resolution scaling for OpenAI: rough multipliers (2K ≈ 2x, 4K ≈ 4x token-metered)
_OPENAI_RESOLUTION_MULT = {None: 1.0, "1K": 1.0, "2K": 2.5, "4K": 6.0}

# Google flat per-image (Gemini Image / Imagen) keyed by max-edge resolution.
# Rough public rates (Vertex pricing + cloudprice.net); refine as pricing changes.
_GOOGLE_PER_IMAGE = {
  "gemini-3-pro-image-preview":     {None: 0.134, "1K": 0.134, "2K": 0.134, "4K": 0.24},
  "gemini-3.1-flash-image-preview": {None: 0.067, "1K": 0.067, "2K": 0.101, "4K": 0.151},
  "gemini-3.1-flash-lite-image":    {None: 0.034, "1K": 0.034, "2K": 0.05, "4K": 0.076},
  "gemini-2.5-flash-image":         {None: 0.04, "1K": 0.04, "2K": 0.13, "4K": 0.24},
  "imagen-4.0-generate-001":        {None: 0.04, "1K": 0.04, "2K": 0.04, "4K": 0.04},
  "imagen-4.0-fast-generate-001":   {None: 0.02, "1K": 0.02, "2K": 0.02, "4K": 0.02},
  "imagen-4.0-ultra-generate-001":  {None: 0.06, "1K": 0.06, "2K": 0.06, "4K": 0.06},
}


def estimate(*, provider: str, model_id: str, n: int = 1,
             quality: str | None = None, resolution: str | None = None) -> float:
  """Return rough USD cost for `n` images. Returns 0.0 if unknown model."""
  if provider == "openai":
    base = _OPENAI_BASE_PER_IMAGE.get(model_id, {}).get(quality or "medium")
    if base is None:
      return 0.0
    return n * base * _OPENAI_RESOLUTION_MULT.get(resolution, 1.0)
  if provider == "google":
    table = _GOOGLE_PER_IMAGE.get(model_id)
    if not table:
      return 0.0
    return n * table.get(resolution, table[None])
  return 0.0
