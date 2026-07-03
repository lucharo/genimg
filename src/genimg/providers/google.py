"""Google Gemini Image / Imagen provider.

Gemini Image returns one image per generate_content call → uses IImageGen template parallelism.
Imagen accepts number_of_images server-side → overrides generate() with a single batched call.
"""
from __future__ import annotations

import time
from pathlib import Path

from google.genai import types
from google.genai.errors import ClientError, ServerError
from PIL import Image

from ..auth.google import get_client
from ..interfaces import GenerateRequest, GenerateResult, IImageGen, ProbeResult


def _is_imagen(model_id: str) -> bool:
  return model_id.startswith("imagen-")


class GeminiImageGen(IImageGen):
  def __init__(self, region: str = "global", project: str | None = None):
    self.region = region
    self.project = project

  def _client(self, region: str | None = None):
    return get_client(region=region or self.region, project=self.project)

  def generate(self, req: GenerateRequest) -> GenerateResult:
    """Imagen's natural mode is one batched call — kept unless --mode parallel or
    diverse per-variant prompts force a fan-out. Gemini uses template parallelism,
    or _generate_batch on explicit --mode batch."""
    if _is_imagen(req.model) and req.mode != "parallel" and not req.prompt_variants:
      return self._generate_imagen_batched(req)
    try:
      return super().generate(req)
    except ClientError as e:
      raise self._friendly(e, req) from e

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    if _is_imagen(req.model):
      return self._generate_imagen_single(req, i)
    client = self._client(req.region)
    contents: list = [req.prompt]
    for ref in req.refs:
      contents.append(Image.open(ref))
    if req.input:
      contents.append(Image.open(req.input))

    image_kwargs = {}
    if req.aspect_ratio:
      image_kwargs["aspect_ratio"] = req.aspect_ratio
    if req.resolution:
      image_kwargs["image_size"] = req.resolution
    config = types.GenerateContentConfig(
      response_modalities=["TEXT", "IMAGE"],
      image_config=types.ImageConfig(**image_kwargs) if image_kwargs else None,
    )

    resp = self._call_with_retry(client, req.model, contents, config)
    out = self.numbered_path(req.output, i, req.n)
    for part in resp.parts:
      if part.inline_data is not None:
        part.as_image().save(out)
        return out
      if part.text:
        print(f"[genimg/google] model said: {part.text}")
    raise RuntimeError("No image returned. Likely a safety filter — rephrase the prompt.")

  def _generate_batch(self, req: GenerateRequest) -> list[Path]:
    """--mode batch on Gemini: ONE generate_content call asked to emit all n images.
    Unlike OpenAI/Imagen n>1 (independent samples of one prompt), the model sees the
    whole batch, so with req.diverse it can deliberately differentiate the takes.
    Multi-image output is prompt-instructed, i.e. best-effort: partial results are
    kept with a warning rather than discarded."""
    client = self._client(req.region)
    header = f"Generate exactly {req.n} separate images"
    if req.diverse:
      header += (", each a deliberately different interpretation — vary style, "
                 "composition, palette, and mood; no two alike")
    contents: list = [f"{header}: {req.prompt}"]
    for ref in req.refs:
      contents.append(Image.open(ref))
    if req.input:
      contents.append(Image.open(req.input))

    image_kwargs = {}
    if req.aspect_ratio:
      image_kwargs["aspect_ratio"] = req.aspect_ratio
    if req.resolution:
      image_kwargs["image_size"] = req.resolution
    config = types.GenerateContentConfig(
      response_modalities=["TEXT", "IMAGE"],
      image_config=types.ImageConfig(**image_kwargs) if image_kwargs else None,
    )

    resp = self._call_with_retry(client, req.model, contents, config)
    paths: list[Path] = []
    for part in resp.parts:
      if part.inline_data is not None and len(paths) < req.n:
        out = self.numbered_path(req.output, len(paths), req.n)
        part.as_image().save(out)
        paths.append(out)
    if not paths:
      raise RuntimeError("No image returned. Likely a safety filter — rephrase the prompt.")
    if len(paths) < req.n:
      print(f"[genimg/google] batch returned {len(paths)}/{req.n} images "
            f"(multi-image output is model-discretionary; --mode parallel guarantees n)")
    return paths

  def _generate_imagen_single(self, req: GenerateRequest, i: int) -> Path:
    """One Imagen image for one prompt variant (diverse mode can't use the batched call)."""
    client = self._client(req.region)
    cfg_kwargs = {
      "number_of_images": 1,
      "aspect_ratio": req.aspect_ratio or "1:1",
      "output_mime_type": "image/png",
    }
    if req.resolution:
      cfg_kwargs["image_size"] = req.resolution
    resp = client.models.generate_images(
      model=req.model, prompt=req.prompt, config=types.GenerateImagesConfig(**cfg_kwargs),
    )
    out = self.numbered_path(req.output, i, req.n)
    resp.generated_images[0].image.save(str(out))
    return out

  def _generate_imagen_batched(self, req: GenerateRequest) -> GenerateResult:
    client = self._client(req.region)
    cfg_kwargs = {
      "number_of_images": req.n,
      "aspect_ratio": req.aspect_ratio or "1:1",
      "output_mime_type": "image/png",
    }
    if req.resolution:
      cfg_kwargs["image_size"] = req.resolution
    config = types.GenerateImagesConfig(**cfg_kwargs)
    try:
      resp = client.models.generate_images(model=req.model, prompt=req.prompt, config=config)
    except ClientError as e:
      raise self._friendly(e, req) from e
    paths: list[Path] = []
    for i, gen in enumerate(resp.generated_images):
      out = self.numbered_path(req.output, i, req.n)
      gen.image.save(str(out))
      paths.append(out)
    return GenerateResult(paths=paths, model_used=req.model)

  def probe(self, model: str, region: str | None = None) -> ProbeResult:
    try:
      client = self._client(region)
      if _is_imagen(model):
        client.models.generate_images(
          model=model, prompt="test",
          config=types.GenerateImagesConfig(number_of_images=1, output_mime_type="image/png"),
        )
      else:
        client.models.generate_content(
          model=model, contents=["test"],
          config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
      return ProbeResult(model=model, status="working")
    except ClientError as e:
      code = getattr(e, "code", None)
      if code in (404, 403):
        return ProbeResult(model=model, status=str(code), detail=str(e)[:200])
      return ProbeResult(model=model, status="error", detail=f"{code}: {str(e)[:200]}")
    except ServerError as e:
      return ProbeResult(model=model, status="error", detail=str(e)[:200])
    except Exception as e:
      return ProbeResult(model=model, status="error", detail=f"{type(e).__name__}: {str(e)[:200]}")

  @staticmethod
  def _call_with_retry(client, model, contents, config, max_retries: int = 5):
    for attempt in range(max_retries):
      try:
        return client.models.generate_content(model=model, contents=contents, config=config)
      except ClientError as e:
        if getattr(e, "code", None) == 429 and attempt < max_retries - 1:
          wait = 2 ** attempt * 5
          print(f"[genimg/google] rate-limited, retrying in {wait}s ({attempt + 1}/{max_retries})")
          time.sleep(wait)
        else:
          raise

  @staticmethod
  def _friendly(e: ClientError, req: GenerateRequest) -> RuntimeError:
    code = getattr(e, "code", None)
    if code == 404:
      return RuntimeError(
        f"model {req.model!r} not available on Vertex region {req.region!r}. "
        f"Hint: `genimg models` — check status, try a different region or alias."
      )
    if code == 403:
      return RuntimeError(
        f"Vertex permission denied for {req.model!r}. "
        f"Check CLAUDE_GCP_CRED service account access. Run `genimg auth`."
      )
    return RuntimeError(f"Vertex error {code}: {str(e)[:200]}")
