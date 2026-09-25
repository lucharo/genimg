"""Google Gemini Image provider."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from google.genai import types
from google.genai.errors import ClientError, ServerError
from PIL import Image

from ..auth import google as auth_google
from ..auth.base import AuthProfile
from ..auth.google import get_client
from ..interfaces import GenerateRequest, GenerateResult, IImageGen, ProbeResult
from .base import ALL_ASPECTS, Capabilities, Provider
from .listing import error_results, listed_model_ids, results_from_model_ids

_GEMINI_ASPECTS = frozenset({"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"})

# Rough public per-image rates (Vertex pricing + cloudprice.net); keyed by stable model id and
# max-edge resolution. None = provider default size.
_PER_IMAGE: dict[str, dict[str | None, float]] = {
  "gemini-3-pro-image":          {None: 0.134, "1K": 0.134, "2K": 0.134, "4K": 0.24},
  "gemini-3.1-flash-image":      {None: 0.067, "512": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
  "gemini-3.1-flash-lite-image": {None: 0.034, "1K": 0.034, "2K": 0.05, "4K": 0.076},
}


def _stable_id(model_id: str) -> str:
  """Saved metadata may still carry a retired `-preview` id; price and size it like the GA id."""
  return model_id[: -len("-preview")] if model_id.endswith("-preview") else model_id


class GeminiImageGen(IImageGen):
  def __init__(self, region: str = "global", project: str | None = None,
               profile: AuthProfile | None = None):
    self.region = region
    self.project = project
    self.profile = profile

  def _client(self, region: str | None = None):
    return get_client(region=region or self.region, project=self.project, profile=self.profile)

  def generate(self, req: GenerateRequest) -> GenerateResult:
    """Use template parallelism, or one Gemini call on explicit --mode batch."""
    try:
      return super().generate(req)
    except ClientError as e:
      raise self._friendly(e, req) from e

  @staticmethod
  def _config(req: GenerateRequest) -> types.GenerateContentConfig:
    image_kwargs = {}
    if req.aspect_ratio:
      image_kwargs["aspect_ratio"] = req.aspect_ratio
    if req.resolution:
      image_kwargs["image_size"] = req.resolution
    return types.GenerateContentConfig(
      response_modalities=["TEXT", "IMAGE"],
      image_config=types.ImageConfig(**image_kwargs) if image_kwargs else None,
      thinking_config=(types.ThinkingConfig(thinking_level=req.thinking_level)
                       if req.thinking_level else None),
    )

  @staticmethod
  def _contents(head: str, req: GenerateRequest) -> list:
    contents: list = [head]
    for ref in req.refs:
      contents.append(Image.open(ref))
    if req.input:
      contents.append(Image.open(req.input))
    return contents

  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    client = self._client(req.region)
    resp = self._call_with_retry(client, req.model, self._contents(req.prompt, req), self._config(req))
    out = self.numbered_path(req.output, i, req.n)
    out.parent.mkdir(parents=True, exist_ok=True)
    for part in resp.parts:
      if part.inline_data is not None:
        part.as_image().save(out)
        return out
      if part.text:
        print(f"[genimg/google] model said: {part.text}")
    raise RuntimeError("No image returned. Likely a safety filter — rephrase the prompt.")

  def _generate_batch(self, req: GenerateRequest) -> list[Path]:
    """--mode batch on Gemini: ONE generate_content call asked to emit all n images.
    Unlike OpenAI n>1 (independent samples of one prompt), the model sees the
    whole batch, so with req.diverse it can deliberately differentiate the takes.
    Multi-image output is prompt-instructed, i.e. best-effort: partial results are
    kept with a warning rather than discarded."""
    client = self._client(req.region)
    header = f"Generate exactly {req.n} separate images"
    if req.diverse:
      header += (", each a deliberately different interpretation — vary style, "
                 "composition, palette, and mood; no two alike")
    resp = self._call_with_retry(client, req.model, self._contents(f"{header}: {req.prompt}", req),
                                 self._config(req))
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

  def probe(self, model: str, region: str | None = None) -> ProbeResult:
    try:
      client = self._client(region)
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
        f"Check the service account's access. Run `genimg auth`."
      )
    return RuntimeError(f"Vertex error {code}: {str(e)[:200]}")


class GoogleProvider(Provider):
  name = "google"
  label = "Google · Gemini"
  alias_prefix = "gdm"
  auth_modes = auth_google.MODES
  flags = frozenset({"thinking", "region", "project"})
  listing_is_exhaustive = False  # Vertex models.list() omits Model Garden publisher models
  order = 10

  def capabilities(self, model_id: str) -> Capabilities:
    mid = _stable_id(model_id)
    if mid.startswith("gemini-3.1-flash-lite-image"):
      # Thinking levels: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image
      # ("Thinking: Supported (minimal and high)", read 2026-09-25).
      return Capabilities(resolutions=frozenset({"1K"}), aspect_ratios=ALL_ASPECTS,
                          thinking_levels=("minimal", "high"), batch=True)
    if mid.startswith("gemini-3.1-flash-image"):
      return Capabilities(resolutions=frozenset({"512", "1K", "2K", "4K"}), aspect_ratios=ALL_ASPECTS,
                          thinking_levels=("minimal", "high"), batch=True)
    if mid.startswith("gemini-3-pro-image"):
      return Capabilities(resolutions=frozenset({"1K", "2K", "4K"}), aspect_ratios=_GEMINI_ASPECTS, batch=True)
    # Any other (inferred) Gemini Image id: provider default size, classic aspect set.
    return Capabilities(resolutions=frozenset(), aspect_ratios=_GEMINI_ASPECTS, batch=True)

  def infer_model(self, model_id: str):
    from ..registry import ModelSpec
    mid = model_id.lower()
    if mid.startswith("gemini-") and "image" in mid:
      return ModelSpec("google", model_id, region="global", quality_rank=0)
    return None

  def price(self, model_id: str, quality: str | None = None, resolution: str | None = None,
            aspect: str | None = None) -> float | None:
    table = _PER_IMAGE.get(_stable_id(model_id))
    if not table:
      return None
    return table.get(resolution, table[None])

  def make(self, profile: AuthProfile | None = None, **kw: Any) -> IImageGen:
    return GeminiImageGen(profile=profile, **kw)

  def probe_listed(self, entries, profile: AuthProfile | None = None) -> dict[str, ProbeResult]:
    """One models.list() per region cohort. On Vertex, models.list() may enumerate only the
    project's own/tuned models, not the Model Garden catalog, so "missing" is unconfirmed,
    not absent."""
    by_region: dict[str, list] = {}
    for alias, spec in entries:
      by_region.setdefault(spec.region or "global", []).append((alias, spec))

    def one(region: str, cohort: list) -> dict[str, ProbeResult]:
      try:
        client = get_client(region=region, profile=profile)
        return results_from_model_ids(cohort, listed_model_ids(client.models.list()))
      except ClientError as e:
        code = getattr(e, "code", None)
        return error_results(cohort, str(code) if code in (403, 404) else "error", f"{code}: {str(e)}")
      except ServerError as e:
        return error_results(cohort, "error", str(e))
      except Exception as e:
        return error_results(cohort, "error", f"{type(e).__name__}: {e}")

    out: dict[str, ProbeResult] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(by_region))) as ex:
      for result in ex.map(lambda kv: one(*kv), by_region.items()):
        out.update(result)
    return out

  def probe_default(self) -> tuple[str, str | None]:
    return "gemini-3.1-flash-image", "global"
