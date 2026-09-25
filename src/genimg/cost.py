"""Per-image cost estimation. Price tables live on each provider (`Provider.price`); the
OpenAI provider counts image-output tokens the way OpenAI's calculator does.

These are coarse estimates — actual billing varies by tier, batch, and exact pixel count.
"""
from __future__ import annotations

from typing import Any


def estimate(*, provider: str, model_id: str, n: int = 1,
             quality: str | None = None, resolution: str | None = None,
             aspect_ratio: str | None = None) -> float | None:
  """Return rough USD cost for `n` images, or None when no estimate is available."""
  from .providers import get
  try:
    per_image = get(provider).price(model_id, quality, resolution, aspect_ratio)
  except ValueError:
    return None
  return None if per_image is None else n * per_image


def format_usd(value: float | None) -> str:
  return "unknown" if value is None else f"${value:.4f}"


def api_equivalent(*, provider: str, model_id: str, output: dict[str, Any],
                   quality: str | None = None, resolution: str | None = None,
                   aspect_ratio: str | None = None) -> dict[str, Any]:
  """Output-only comparison, separate from billing. Native settings are unreported."""
  from .provenance import generators
  from .providers import get
  from .providers import openai as oai
  try:
    billing = get(provider).billing
  except ValueError:
    billing = "api"
  dimensions = output.get("dimensions", {})
  width, height = dimensions.get("width"), dimensions.get("height")
  if billing != "subscription":
    if provider == "openai" and oai.api_size(width, height):
      value = oai.price_at(model_id, width, height, quality)
    else:
      value = estimate(provider=provider, model_id=model_id, quality=quality,
                       resolution=resolution, aspect_ratio=aspect_ratio)
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
            "assumptions": "API model inferred from unverified C2PA; quality unknown. Low-to-high output price at the reported size; excludes input tokens, not a billing quote."}
  if inferred and width and height:
    low = oai.price_at(inferred, width, height, "low")
    high = oai.price_at(inferred, width, height, "high")
    result.update(usd_min=round(low, 6), usd_max=round(high, 6))
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
  if meta.get("billing"):
    return meta["billing"]
  from .providers import get
  try:
    return get(meta.get("provider") or "").billing
  except ValueError:
    return "api"
