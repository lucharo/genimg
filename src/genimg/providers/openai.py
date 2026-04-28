"""OpenAI / Azure OpenAI image provider (gpt-image-* family).

Per-image latency on Azure jules-aiml-2 is multi-minute even at medium quality and
the deployment does NOT parallelize a single n>1 request server-side. We therefore
split into n parallel n=1 calls via the IImageGen base template.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
from pathlib import Path

from openai import APIStatusError, AuthenticationError, NotFoundError

from ..auth.openai import get_client
from ..interfaces import GenerateRequest, IImageGen, ProbeResult

# 2D map: (resolution, aspect) → WxH for gpt-image-2.
# All edges are multiples of 16, max edge ≤3840, total px in [655k, 8.3M].
# 4K + 4:3/3:4 is rejected upstream in _validate_provider_flags (would exceed 8.3M cap).
_SIZE_MAP = {
  ("1K", "1:1"):  "1024x1024",
  ("1K", "4:3"):  "1536x1024",
  ("1K", "3:4"):  "1024x1536",
  ("1K", "16:9"): "1536x1024",
  ("1K", "9:16"): "1024x1536",
  ("2K", "1:1"):  "2048x2048",
  ("2K", "4:3"):  "2048x1536",
  ("2K", "3:4"):  "1536x2048",
  ("2K", "16:9"): "2048x1152",
  ("2K", "9:16"): "1152x2048",
  ("4K", "1:1"):  "2880x2880",
  ("4K", "16:9"): "3840x2160",
  ("4K", "9:16"): "2160x3840",
}


class OpenAIImageGen(IImageGen):
  def __init__(self, force_auth: str | None = None):
    self.force_auth = force_auth

  def _client(self):
    return get_client(force=self.force_auth)

  def _size_for(self, req: GenerateRequest) -> str:
    """Pick OpenAI size honoring BOTH resolution and aspect_ratio when given."""
    res = req.resolution or "1K"
    ar = req.aspect_ratio or "1:1"
    return _SIZE_MAP.get((res, ar), "1024x1024")

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    client = self._client()
    size = self._size_for(req)
    quality = req.quality or "medium"  # high is 30-90s/image; medium is the fast-ish default
    inputs: list[Path] = ([req.input] if req.input else []) + list(req.refs)

    try:
      if inputs:
        with ExitStack() as stack:
          handles = [stack.enter_context(open(p, "rb")) for p in inputs]
          resp = client.images.edit(
            model=req.model, image=handles, prompt=req.prompt,
            size=size, quality=quality, n=1,
          )
      else:
        resp = client.images.generate(
          model=req.model, prompt=req.prompt,
          size=size, quality=quality, n=1,
        )
    except NotFoundError as e:
      raise RuntimeError(
        f"model {req.model!r} not deployed on this OpenAI endpoint. "
        f"Hint: `genimg models` — try -m oai:gi2 (or another with status=working)."
      ) from e
    except AuthenticationError as e:
      raise RuntimeError(
        "OpenAI auth failed. Check OPENAI_API_KEY (and OPENAI_BASE_URL for Azure). "
        "Run `genimg auth` to inspect."
      ) from e
    except APIStatusError as e:
      raise RuntimeError(f"OpenAI API error {e.status_code}: {str(e)[:200]}") from e

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
