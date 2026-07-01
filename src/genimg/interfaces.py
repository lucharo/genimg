"""Provider-neutral types + IImageGen base class with shared parallel template."""
from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Resolution = Literal["1K", "2K", "4K"]
AspectRatio = Literal["1:1", "3:4", "4:3", "9:16", "16:9"]
Quality = Literal["low", "medium", "high", "auto"]


class GenerateRequest(BaseModel):
  prompt: str
  output: Path
  model: str
  refs: list[Path] = Field(default_factory=list)
  input: Path | None = None
  resolution: Resolution | None = None
  aspect_ratio: AspectRatio | None = None
  n: int = 1
  quality: Quality | None = None
  region: str | None = None
  project: str | None = None


class GenerateResult(BaseModel):
  paths: list[Path]
  model_used: str
  cost_usd: float | None = None
  errors: list[str] = Field(default_factory=list)  # per-variant failures on a partially-successful n>1 batch


class ProbeResult(BaseModel):
  model: str
  status: Literal["listed", "missing", "working", "404", "403", "auth", "error"]
  detail: str = ""


class IImageGen(ABC):
  """Template-method base. Subclasses implement _generate_single_image() and probe();
  generate() handles n=1 directly and dispatches n>1 in parallel."""

  max_parallel: int = 5

  @abstractmethod
  def _generate_single_image(self, req: GenerateRequest, i: int) -> Path:
    """Generate exactly one image. Index `i` is used to derive numbered output paths."""

  @abstractmethod
  def probe(self, model: str, region: str | None = None) -> ProbeResult: ...

  def generate(self, req: GenerateRequest) -> GenerateResult:
    if req.n == 1:
      return GenerateResult(paths=[self._generate_single_image(req, 0)], model_used=req.model)
    # Run variants independently: a batch tool should keep the images that succeeded
    # rather than discard everything (and orphan already-written files) on one failure.
    results: dict[int, Path] = {}
    errors: dict[int, Exception] = {}
    with ThreadPoolExecutor(max_workers=min(req.n, self.max_parallel)) as ex:
      futures = {ex.submit(self._generate_single_image, req, i): i for i in range(req.n)}
      for future in as_completed(futures):
        i = futures[future]
        try:
          results[i] = future.result()
        except Exception as e:  # noqa: BLE001 — re-raised (all-fail) or reported (partial) below
          errors[i] = e
    if not results:
      raise errors[min(errors)]  # all variants failed — surface the first (keeps provider-friendly mapping)
    ordered_paths = [results[i] for i in sorted(results)]
    error_msgs = [f"#{i + 1}: {type(errors[i]).__name__}: {errors[i]}" for i in sorted(errors)]
    return GenerateResult(paths=ordered_paths, model_used=req.model, errors=error_msgs)

  @staticmethod
  def numbered_path(out: Path, i: int, n: int) -> Path:
    """Shared filename helper: <stem>_<i+1>.<ext> for n>1, bare path for n=1."""
    if n == 1:
      return out
    return out.with_name(f"{out.stem}_{i + 1}{out.suffix}")
