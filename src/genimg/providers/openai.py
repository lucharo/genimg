"""OpenAI / Azure OpenAI image provider (gpt-image-* family).

Per-image latency can be multi-minute even at medium quality, and some Azure
deployments do NOT parallelize a single n>1 request server-side. We therefore
split into n parallel n=1 calls via the IImageGen base template.
"""
from __future__ import annotations

import base64
import math
import re
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from openai import APIStatusError, AuthenticationError, NotFoundError

from ..auth import openai as auth_openai
from ..auth.base import AuthProfile
from ..auth.openai import get_client
from ..interfaces import GenerateRequest, IImageGen, ProbeResult
from .base import Capabilities, Provider
from .listing import error_results, listed_model_ids, results_from_model_ids

# 2D map: (resolution, aspect) → WxH for gpt-image-2 and 2.5. Each entry honors the
# requested aspect EXACTLY (no 3:2 substitutions for 4:3 or 16:9).
# Constraints: edges mult of 16, max edge ≤3840, total px in [655_360, 8_294_400].
# Combos NOT in this map are rejected by the CLI (Capabilities.supports_size) and by
# _size_for() for library callers, so neither path silently substitutes a wrong size.
_SIZE_MAP = {
  # 1K (~1024 long edge). 16:9 / 9:16 at 1K would be <655k px, rejected upstream.
  ("1K", "1:1"):  "1024x1024",
  ("1K", "4:3"):  "1024x768",
  ("1K", "3:4"):  "768x1024",
  # 2K family — full aspect set.
  ("2K", "1:1"):  "2048x2048",
  ("2K", "4:3"):  "2048x1536",
  ("2K", "3:4"):  "1536x2048",
  ("2K", "16:9"): "2048x1152",
  ("2K", "9:16"): "1152x2048",
  # 4K family — 4:3/3:4 would exceed 8.3M px cap, rejected upstream.
  ("4K", "1:1"):  "2880x2880",
  ("4K", "16:9"): "3840x2160",
  ("4K", "9:16"): "2160x3840",
}
# GPT Image 1, 1 mini and 1.5 take only 1024x1024, 1536x1024 and 1024x1536; arbitrary WxH is
# gpt-image-2 and 2.5 only (`size` in
# https://developers.openai.com/api/reference/resources/images/methods/generate, read 2026-09-25).
# Of genimg's (resolution, aspect) pairs, only 1K 1:1 lands on one of those sizes.
_LEGACY_SIZE_MAP = {("1K", "1:1"): "1024x1024"}
_LEGACY_MODEL = re.compile(r"gpt-image-1(\.5|-mini)?(-\d{4}-\d{2}-\d{2})?")


def size_map(model_id: str) -> dict[tuple[str, str], str]:
  """(resolution, aspect) → WxH for the sizes `model_id` accepts, dated snapshots included."""
  return _LEGACY_SIZE_MAP if _LEGACY_MODEL.fullmatch(model_id) else _SIZE_MAP

_INPUT_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_INPUT_MB = 50
_MAX_INPUTS = 16

# GPT Image 2 and 2.5 are priced per image-output token. The count comes from OpenAI's own
# calculator (the script behind
# https://developers.openai.com/api/docs/guides/image-generation#calculating-costs, served as
# /_astro/GptImageTokenCalculator.react.<hash>.js; read 2026-09-24): edge * round(edge / aspect)
# tokens, scaled by pixel count, see output_tokens(). Real `usage` fields measured against
# api.openai.com on 2026-09-19 match it exactly for both families. The rate is
# https://developers.openai.com/api/docs/pricing; text input ($5 per million tokens, a few
# hundred per prompt) is not included. Azure is priced at the direct rate: the Azure retail
# price API listed no gpt-image-2/2.5 meters on 2026-09-24 and its gpt-image-1 meter matched.
_TOKEN_GRID = {
  "gpt-image-2":   {"low": 16, "medium": 48, "high": 96},
  "gpt-image-2.5": {"low": 16, "medium": 24, "high": 48, "xhigh": 64, "max": 96},
}
OUTPUT_USD_PER_M = 30.0
# Pixel-count range the API accepts; an output outside it was not produced at that size.
_PIXEL_RANGE = (655_360, 8_294_400)
# Older models: the image guide's legacy per-image table ("Earlier GPT Image models"), by size.
_LEGACY_PER_IMAGE = {
  "gpt-image-1.5": {
    "1024x1024": {"low": 0.009, "medium": 0.034, "high": 0.133},
    "1024x1536": {"low": 0.013, "medium": 0.05, "high": 0.2},
    "1536x1024": {"low": 0.013, "medium": 0.05, "high": 0.2},
  },
  "gpt-image-1": {
    "1024x1024": {"low": 0.011, "medium": 0.042, "high": 0.167},
    "1024x1536": {"low": 0.016, "medium": 0.063, "high": 0.25},
    "1536x1024": {"low": 0.016, "medium": 0.063, "high": 0.25},
  },
  "gpt-image-1-mini": {
    "1024x1024": {"low": 0.005, "medium": 0.011, "high": 0.036},
    "1024x1536": {"low": 0.006, "medium": 0.015, "high": 0.052},
    "1536x1024": {"low": 0.006, "medium": 0.015, "high": 0.052},
  },
}
_GPT_IMAGE_25 = re.compile(r"gpt-image-2\.5-(sunburst|flare)(-\d{4}-\d{2}-\d{2})?")
_GPT_IMAGE_2 = re.compile(r"gpt-image-2(-\d{4}-\d{2}-\d{2})?")


def token_family(model_id: str) -> str | None:
  """Calculator family for a model id (dated snapshots included), or None."""
  if _GPT_IMAGE_25.fullmatch(model_id):
    return "gpt-image-2.5"
  if _GPT_IMAGE_2.fullmatch(model_id):
    return "gpt-image-2"
  return None


def _effective_quality(quality: str | None) -> str:
  # `auto` is estimated as `medium`; the real count depends on the generated image.
  return "medium" if quality in (None, "auto") else quality


def output_tokens(model_id: str, width: int, height: int, quality: str | None = None) -> int | None:
  """Image output tokens for one image, exactly as OpenAI's calculator counts them."""
  family = token_family(model_id)
  if family is None:
    return None
  edge = _TOKEN_GRID[family].get(_effective_quality(quality))
  if edge is None or width <= 0 or height <= 0:
    return None
  raw = edge / (max(width, height) / min(width, height))
  floor = math.floor(raw)
  # A half rounds to even, as the calculator does; everything else rounds to nearest.
  short_tokens = floor + floor % 2 if raw - floor == 0.5 else round(raw)
  return math.ceil(edge * short_tokens * (2_000_000 + width * height) / 4_000_000)


def price_at(model_id: str, width: int, height: int, quality: str | None = None) -> float | None:
  """USD for one image at an exact WxH, output tokens only."""
  tokens = output_tokens(model_id, width, height, quality)
  if tokens is not None:
    return tokens * OUTPUT_USD_PER_M / 1_000_000
  legacy = _LEGACY_PER_IMAGE.get(model_id)
  if legacy is None:
    return None
  quality = _effective_quality(quality)
  documented = legacy.get(f"{width}x{height}", {}).get(quality)
  if documented is not None:
    return documented
  # Undocumented sizes: scale the square row by pixel area (rough).
  square = legacy["1024x1024"].get(quality)
  return None if square is None else square * width * height / 1024**2


def api_size(width: int | None, height: int | None) -> bool:
  """True when WxH is a size the API can have produced."""
  return bool(width and height and _PIXEL_RANGE[0] <= width * height <= _PIXEL_RANGE[1])


def quality_options(model_id: str) -> list[str]:
  """Documented quality levels, including the 2.5 models' dated snapshots."""
  if re.fullmatch(r"gpt-image-2\.5-(sunburst|flare)(-\d{4}-\d{2}-\d{2})?", model_id):
    return ["low", "medium", "high", "xhigh", "max", "auto"]
  return ["low", "medium", "high", "auto"]


def size_error(resolution: str | None, aspect_ratio: str | None, model_id: str = "") -> str:
  """Explain why a (resolution, aspect) pair is not in `model_id`'s size table."""
  res, ar = resolution or "1K", aspect_ratio or "1:1"
  if size_map(model_id) is _LEGACY_SIZE_MAP:
    return (f"OpenAI: {model_id} takes only 1K 1:1 (1024x1024) of genimg's sizes. "
            "Drop -r/-a, or use -m oai:gi2 for 2K, 4K and other aspect ratios.")
  if res == "4K" and ar in ("4:3", "3:4"):
    return "OpenAI: 4K + 4:3/3:4 exceeds the total pixel cap (8.3M). Use 2K + 4:3/3:4, or 4K + 16:9/9:16."
  if res == "1K" and ar in ("16:9", "9:16"):
    return ("OpenAI: 16:9/9:16 at 1K falls below the 655k pixel min. Pass -r 2K (→ 2048x1152 / 1152x2048), "
            "or drop --aspect-ratio for the 1K square default.")
  supported = ", ".join(f"{r}+{a}" for r, a in sorted(_SIZE_MAP))
  return f"OpenAI: unsupported ({res}, {ar}) size combo. Supported: {supported}."


class OpenAIImageGen(IImageGen):
  def __init__(self, force_auth: str | None = None, profile: AuthProfile | None = None):
    self.force_auth = force_auth
    self.profile = profile

  def _client(self):
    return get_client(force=self.force_auth, profile=self.profile)

  def _size_for(self, req: GenerateRequest) -> str:
    """Pick OpenAI size honoring BOTH resolution and aspect_ratio. Raises on unsupported combos
    so library callers (who bypass CLI validation) don't silently get a 1024² fallback."""
    res = req.resolution or "1K"
    ar = req.aspect_ratio or "1:1"
    sizes = size_map(req.model)
    size = sizes.get((res, ar))
    if size is None:
      raise RuntimeError(
        f"OpenAI: ({res}, {ar}) is not a supported size combo for {req.model}. "
        f"Supported: {sorted(sizes.keys())}"
      )
    return size

  def _request(self, req: GenerateRequest):
    """One single-image API call with friendly error mapping. Deliberately no n>1
    variant: a batched gpt-image request returns near-duplicate independent samples
    (verified live) — the CLI rejects --mode batch on OpenAI as wasted spend."""
    size = self._size_for(req)
    quality = req.quality or "medium"  # high is 30-90s/image; medium is the fast-ish default
    if quality not in quality_options(req.model):
      raise RuntimeError(f"OpenAI: quality {quality!r} is not supported by {req.model}.")
    client = self._client()
    inputs: list[Path] = ([req.input] if req.input else []) + list(req.refs)

    try:
      if inputs:
        with ExitStack() as stack:
          handles = [stack.enter_context(open(p, "rb")) for p in inputs]
          return client.images.edit(
            model=req.model, image=handles, prompt=req.prompt,
            size=size, quality=quality, n=1,
          )
      return client.images.generate(
        model=req.model, prompt=req.prompt,
        size=size, quality=quality, n=1,
      )
    except NotFoundError as e:
      raise RuntimeError(
        f"model {req.model!r} not deployed on this OpenAI endpoint. "
        f"Hint: `genimg models` — try -m oai:gi2 (or another with status=listed)."
      ) from e
    except AuthenticationError as e:
      raise RuntimeError(
        "OpenAI auth failed. Check OPENAI_API_KEY (and the Azure endpoint for azure profiles). "
        "Run `genimg auth` to inspect."
      ) from e
    except APIStatusError as e:
      raise RuntimeError(f"OpenAI API error {e.status_code}: {str(e)[:200]}") from e

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    resp = self._request(req)
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(resp.data[0].b64_json))
    return out

  def probe(self, model: str, region: str | None = None) -> ProbeResult:
    try:
      self._client().images.generate(model=model, prompt="test", size="1024x1024", quality="low", n=1)
      return ProbeResult(model=model, status="working")
    except NotFoundError as e:
      return ProbeResult(model=model, status="404", detail=str(e)[:200])
    except AuthenticationError as e:
      return ProbeResult(model=model, status="auth", detail=str(e)[:200])
    except APIStatusError as e:
      status = "403" if e.status_code == 403 else ("404" if e.status_code == 404 else "error")
      return ProbeResult(model=model, status=status, detail=f"{e.status_code}: {str(e)[:200]}")
    except Exception as e:
      return ProbeResult(model=model, status="error", detail=f"{type(e).__name__}: {str(e)[:200]}")


class OpenAIProvider(Provider):
  name = "openai"
  label = "OpenAI"
  alias_prefix = "oai"
  auth_modes = auth_openai.MODES
  flags = frozenset({"quality", "auth"})
  order = 20

  def capabilities(self, model_id: str) -> Capabilities:
    sizes = size_map(model_id)
    return Capabilities(
      resolutions=frozenset(r for r, _ in sizes),
      aspect_ratios=frozenset(a for _, a in sizes),
      qualities=tuple(quality_options(model_id)),
      batch=False,
      max_inputs=_MAX_INPUTS, input_exts=_INPUT_EXTS, max_input_mb=_MAX_INPUT_MB,
      sizes=dict(sizes), default_resolution="1K", default_aspect="1:1",
    )

  def infer_model(self, model_id: str):
    """Only the gpt-image request shape is inferred. `dall-e-*` is intentionally excluded:
    this provider always sends gpt-image-style size/quality params that DALL-E rejects."""
    from ..registry import ModelSpec
    if model_id.lower().startswith("gpt-image"):
      return ModelSpec("openai", model_id, region=None, quality_rank=0)
    return None

  def price(self, model_id: str, quality: str | None = None, resolution: str | None = None,
            aspect: str | None = None) -> float | None:
    size = size_map(model_id).get((resolution or "1K", aspect or "1:1"))
    if size is None:
      return None
    width, height = (int(v) for v in size.split("x"))
    return price_at(model_id, width, height, quality)

  def make(self, profile: AuthProfile | None = None, **kw: Any) -> IImageGen:
    return OpenAIImageGen(profile=profile, **kw)

  def probe_listed(self, entries, profile: AuthProfile | None = None) -> dict[str, ProbeResult]:
    try:
      client = get_client(profile=profile)
    except RuntimeError as e:  # no usable credentials; "auth" rows are never cached
      return error_results(entries, "auth", str(e))
    try:
      return results_from_model_ids(entries, listed_model_ids(client.models.list()))
    except AuthenticationError as e:
      return error_results(entries, "auth", str(e))
    except APIStatusError as e:
      status = "403" if e.status_code == 403 else ("404" if e.status_code == 404 else "error")
      return error_results(entries, status, f"{e.status_code}: {str(e)}")
    except Exception as e:
      return error_results(entries, "error", f"{type(e).__name__}: {e}")

  def probe_default(self) -> tuple[str, str | None]:
    return "gpt-image-2", None

  def size_error(self, resolution: str | None, aspect: str | None, model_id: str = "") -> str:
    return size_error(resolution, aspect, model_id)
