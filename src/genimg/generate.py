"""High-level dispatch: registry lookup → correct IImageGen impl → generate."""
from __future__ import annotations

from .interfaces import GenerateRequest, GenerateResult, IImageGen
from .providers import GeminiImageGen, OpenAIImageGen
from .registry import resolve


def _provider_for(provider: str, force_openai_auth: str | None = None) -> IImageGen:
  if provider == "google":
    return GeminiImageGen()
  if provider == "openai":
    return OpenAIImageGen(force_auth=force_openai_auth)
  raise ValueError(f"unknown provider {provider!r}")


def generate(req: GenerateRequest, force_openai_auth: str | None = None) -> GenerateResult:
  """Resolve req.model (alias or canonical) and dispatch to the right IImageGen impl."""
  _, spec = resolve(req.model)
  resolved_req = req.model_copy(update={
    "model": spec.model_id,
    "region": req.region or spec.region,
  })
  return _provider_for(spec.provider, force_openai_auth).generate(resolved_req)
