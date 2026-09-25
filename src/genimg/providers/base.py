"""Provider plugin contract and registry.

A `Provider` bundles everything genimg needs to know about one image backend: its auth
modes, per-model capabilities (sizes, qualities, batch support), pricing, structural model
inference, discovery probing and the `IImageGen` factory. Providers self-register on import
(`register(GoogleProvider())`), and every other module (CLI validation, cost, grid, discovery,
setup wizard, Draw Studio) reads the registry instead of branching on provider names.

Adding a provider: subclass `Provider`, add its `AuthProfile` classes, register it in
`providers/__init__.py`, and add curated aliases to `registry.py`. The contract test in
`tests/test_provider_contract.py` checks every registered provider the same way.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from ..auth.base import AuthProfile
from ..interfaces import IImageGen, ProbeResult

if TYPE_CHECKING:
  from ..registry import ModelSpec


ALL_RESOLUTIONS: frozenset[str] = frozenset({"512", "1K", "2K", "4K"})
ALL_ASPECTS: frozenset[str] = frozenset({
  "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1",
  "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
})


@dataclass(frozen=True)
class Capabilities:
  """What one model accepts. Empty `resolutions` means the provider picks the size."""
  resolutions: frozenset[str] = frozenset()
  aspect_ratios: frozenset[str] = frozenset()
  qualities: tuple[str, ...] = ()
  thinking_levels: tuple[str, ...] = ()
  batch: bool = False                 # supports --mode batch (one n-image request)
  max_inputs: int | None = None
  input_exts: frozenset[str] | None = None
  max_input_mb: float | None = None
  # Explicit (resolution, aspect) → "WxH" table. When set, only its keys are valid pairs.
  sizes: dict[tuple[str, str], str] = field(default_factory=dict)
  default_resolution: str | None = None
  default_aspect: str | None = None

  def supports_size(self, resolution: str | None, aspect: str | None) -> bool:
    if self.sizes:
      return (resolution or self.default_resolution or "1K",
              aspect or self.default_aspect or "1:1") in self.sizes
    if resolution is not None and resolution not in self.resolutions:
      return False
    return aspect is None or aspect in self.aspect_ratios

  def resolved_size(self, resolution: str | None, aspect: str | None) -> str | None:
    if not self.sizes:
      return None
    return self.sizes.get((resolution or self.default_resolution or "1K",
                           aspect or self.default_aspect or "1:1"))

  def resolution_options_by_aspect(self) -> dict[str, list[str]]:
    """Studio helper: aspect → ordered resolutions that pair with it."""
    if not self.sizes:
      return {}
    out: dict[str, list[str]] = {}
    for res, asp in sorted(self.sizes, key=lambda k: (_res_order(k[0]), k[1])):
      out.setdefault(asp, []).append(res)
    return out


def _res_order(res: str) -> int:
  return {"512": 0, "1K": 1, "2K": 2, "4K": 3}.get(res, 9)


class Provider(ABC):
  """One image backend. Class attributes describe it; methods answer per-model questions."""

  name: ClassVar[str]                      # "google"
  label: ClassVar[str]                     # "Google · Gemini"
  alias_prefix: ClassVar[str]              # "gdm"
  auth_modes: ClassVar[tuple[type[AuthProfile], ...]] = ()  # detection order
  # CLI flags this provider understands beyond the shared set.
  flags: ClassVar[frozenset[str]] = frozenset()   # {"quality", "auth", "thinking", "region", "project"}
  billing: ClassVar[str] = "api"           # "api" | "subscription"
  runtime_selects_model: ClassVar[bool] = False
  # True when the provider's list endpoint enumerates every servable model, so "missing"
  # means unavailable. False when listing can under-report (Vertex Model Garden).
  listing_is_exhaustive: ClassVar[bool] = True
  order: ClassVar[int] = 50                # display order across providers

  # ── contract ──
  @abstractmethod
  def capabilities(self, model_id: str) -> Capabilities: ...

  @abstractmethod
  def make(self, profile: AuthProfile | None = None, **kw: Any) -> IImageGen:
    """Build the generator bound to a resolved auth profile (None = auto-resolve at call time)."""

  def infer_model(self, model_id: str) -> "ModelSpec | None":
    """Structural inference for an unregistered id; None when the shape isn't ours."""
    return None

  def price(self, model_id: str, quality: str | None = None, resolution: str | None = None,
            aspect: str | None = None) -> float | None:
    """Rough per-image USD, or None when unknown (subscription, unpriced model)."""
    return None

  def price_table(self, model_id: str) -> dict[str, dict[str, float]]:
    """quality ("" when n/a) → resolution ("" when n/a) → USD at the default aspect, plus a
    "resolution|aspect" key per size the provider prices differently. Used by the Draw Studio."""
    caps = self.capabilities(model_id)
    qualities = list(caps.qualities) or [""]
    resolutions = sorted(caps.resolutions, key=_res_order) or [""]
    table: dict[str, dict[str, float]] = {}
    for q in qualities:
      row: dict[str, float] = {}
      for r in resolutions:
        usd = self.price(model_id, q or None, r or None)
        if usd is not None:
          row[r] = usd
      for res, asp in sorted(caps.sizes, key=lambda k: (_res_order(k[0]), k[1])):
        usd = self.price(model_id, q or None, res, asp)
        if usd is not None and usd != row.get(res):
          row[f"{res}|{asp}"] = usd
      if row:
        table[q] = row
    return table

  def probe_listed(self, entries: list[tuple[str, "ModelSpec"]],
                   profile: AuthProfile | None = None) -> dict[str, ProbeResult]:
    """Free availability check for many registry entries (models.list or login status).
    Default: one `probe()` per entry through the generator."""
    gen = self.make(profile)
    return {alias: gen.probe(spec.model_id, spec.region) for alias, spec in entries}

  def probe_default(self) -> tuple[str, str | None]:
    """(model_id, region) for `genimg auth --check`'s tiny live probe."""
    raise NotImplementedError

  def size_error(self, resolution: str | None, aspect: str | None) -> str:
    """Explain a (resolution, aspect) pair outside the explicit size table."""
    supported = ", ".join(f"{r}+{a}" for r, a in sorted(self.capabilities("").sizes))
    return f"{self.label}: unsupported ({resolution or '-'}, {aspect or '-'}) size combo. Supported: {supported}."

  # ── auth helpers ──
  @property
  def modes(self) -> dict[str, type[AuthProfile]]:
    return {cls.mode: cls for cls in self.auth_modes}

  def __repr__(self) -> str:
    return f"<Provider {self.name}>"


# ── registry ──

_PROVIDERS: dict[str, Provider] = {}


def register(provider: Provider) -> Provider:
  _PROVIDERS[provider.name] = provider
  return provider


def get(name: str) -> Provider:
  try:
    return _PROVIDERS[name]
  except KeyError:
    raise ValueError(f"unknown provider {name!r}; registered: {', '.join(sorted(_PROVIDERS))}") from None


def all_providers() -> list[Provider]:
  return sorted(_PROVIDERS.values(), key=lambda p: (p.order, p.name))


def names() -> list[str]:
  return [p.name for p in all_providers()]
