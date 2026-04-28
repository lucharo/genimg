"""OpenAI / Azure OpenAI image provider (gpt-image-* family).

Per-image latency on Azure example-azure-resource is multi-minute even at medium quality and
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

# Resolution preset → WxH for OpenAI sizes (gpt-image-2 supports up to 3840 max edge).
_RES_TO_SIZE = {"1K": "1024x1024", "2K": "2048x2048", "4K": "3840x2160"}
# Aspect ratio overrides resolution preset when both given (aspect wins for shape).
_ASPECT_TO_SIZE = {
  "1:1":  "1024x1024",
  "4:3":  "1536x1024",
  "3:4":  "1024x1536",
  "16:9": "1536x1024",
  "9:16": "1024x1536",
}


class OpenAIImageGen(IImageGen):
  def __init__(self, force_auth: str | None = None):
    self.force_auth = force_auth

  def _client(self):
    return get_client(force=self.force_auth)

  def _size_for(self, req: GenerateRequest) -> str:
    if req.aspect_ratio and req.resolution in (None, "1K"):
      return _ASPECT_TO_SIZE[req.aspect_ratio]
    if req.resolution:
      return _RES_TO_SIZE[req.resolution]
    return "1024x1024"

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
