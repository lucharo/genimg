"""OpenAI / Azure OpenAI image provider (gpt-image-* family).

Per-image latency can be multi-minute even at medium quality, and some Azure
deployments do NOT parallelize a single n>1 request server-side. We therefore
split into n parallel n=1 calls via the IImageGen base template.
"""
from __future__ import annotations

import base64
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

_INPUT_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_INPUT_MB = 50
_MAX_INPUTS = 16

# Per 1024x1024 image, by quality.
# https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
# GPT Image 2.5 has the same token rates as 2 but different token consumption; no per-image
# row until documented (never copy GPT Image 2's estimates).
# https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst
_BASE_PER_IMAGE = {
  "gpt-image-2":      {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053},
  "gpt-image-1.5":    {"low": 0.009, "medium": 0.034, "high": 0.133, "auto": 0.034},
  "gpt-image-1":      {"low": 0.011, "medium": 0.042, "high": 0.167, "auto": 0.042},
  "gpt-image-1-mini": {"low": 0.004, "medium": 0.015, "high": 0.060, "auto": 0.015},
}
# Rough resolution multipliers (2K ≈ 2x, 4K ≈ 4x token-metered).
_RESOLUTION_MULT = {None: 1.0, "1K": 1.0, "2K": 2.5, "4K": 6.0}


def quality_options(model_id: str) -> list[str]:
  """Documented quality levels, including the 2.5 models' dated snapshots."""
  if re.fullmatch(r"gpt-image-2\.5-(sunburst|flare)(-\d{4}-\d{2}-\d{2})?", model_id):
    return ["low", "medium", "high", "xhigh", "max", "auto"]
  return ["low", "medium", "high", "auto"]


def size_error(resolution: str | None, aspect_ratio: str | None) -> str:
  """Explain why a (resolution, aspect) pair is not in the size table."""
  res, ar = resolution or "1K", aspect_ratio or "1:1"
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
    size = _SIZE_MAP.get((res, ar))
    if size is None:
      raise RuntimeError(
        f"OpenAI: ({res}, {ar}) is not a supported size combo. "
        f"Supported: {sorted(_SIZE_MAP.keys())}"
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
    return Capabilities(
      resolutions=frozenset(r for r, _ in _SIZE_MAP),
      aspect_ratios=frozenset(a for _, a in _SIZE_MAP),
      qualities=tuple(quality_options(model_id)),
      batch=False,
      max_inputs=_MAX_INPUTS, input_exts=_INPUT_EXTS, max_input_mb=_MAX_INPUT_MB,
      sizes=dict(_SIZE_MAP), default_resolution="1K", default_aspect="1:1",
    )

  def infer_model(self, model_id: str):
    """Only the gpt-image request shape is inferred. `dall-e-*` is intentionally excluded:
    this provider always sends gpt-image-style size/quality params that DALL-E rejects."""
    from ..registry import ModelSpec
    if model_id.lower().startswith("gpt-image"):
      return ModelSpec("openai", model_id, region=None, quality_rank=0)
    return None

  def price(self, model_id: str, quality: str | None = None, resolution: str | None = None) -> float | None:
    base = _BASE_PER_IMAGE.get(model_id, {}).get(quality or "medium")
    if base is None:
      return None
    return base * _RESOLUTION_MULT.get(resolution, 1.0)

  def base_prices(self) -> dict[str, dict[str, float]]:
    """Per-1024² reference table (low..high), used for C2PA-inferred equivalents."""
    return _BASE_PER_IMAGE

  def make(self, profile: AuthProfile | None = None, **kw: Any) -> IImageGen:
    return OpenAIImageGen(profile=profile, **kw)

  def probe_listed(self, entries, profile: AuthProfile | None = None) -> dict[str, ProbeResult]:
    try:
      client = get_client(profile=profile)
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
