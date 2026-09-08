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

from openai import APIStatusError, AuthenticationError, NotFoundError

from ..auth.openai import get_client
from ..interfaces import GenerateRequest, IImageGen, ProbeResult

# 2D map: (resolution, aspect) → WxH for gpt-image-2 and 2.5. Each entry honors the
# requested aspect EXACTLY (no 3:2 substitutions for 4:3 or 16:9).
# Constraints: edges mult of 16, max edge ≤3840, total px in [655_360, 8_294_400].
# Combos NOT in this map are rejected by _validate_provider_flags (CLI) and
# _size_for() (library callers) so neither path silently substitutes a wrong size.
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


def quality_options(model_id: str) -> list[str]:
  """Documented quality levels, including the 2.5 models' dated snapshots."""
  if re.fullmatch(r"gpt-image-2\.5-(sunburst|flare)(-\d{4}-\d{2}-\d{2})?", model_id):
    return ["low", "medium", "high", "xhigh", "max", "auto"]
  return ["low", "medium", "high", "auto"]


class OpenAIImageGen(IImageGen):
  def __init__(self, force_auth: str | None = None):
    self.force_auth = force_auth

  def _client(self):
    return get_client(force=self.force_auth)

  def _size_for(self, req: GenerateRequest) -> str:
    """Pick OpenAI size honoring BOTH resolution and aspect_ratio. Raises on unsupported combos
    so library callers (who bypass CLI _validate_provider_flags) don't silently get a 1024² fallback."""
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
        "OpenAI auth failed. Check OPENAI_API_KEY (and OPENAI_BASE_URL for Azure). "
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
