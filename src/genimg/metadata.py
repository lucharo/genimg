"""Per-generation metadata sidecar (~/.genimg/metadata/<id>.json).

Records prompt, model, paths, cost, params for searchability + reproducibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.PngImagePlugin import PngInfo

GENIMG_HOME = Path(os.getenv("GENIMG_HOME") or Path.home() / ".genimg")
GEN_DIR = GENIMG_HOME / "generations"
META_DIR = GENIMG_HOME / "metadata"
GRID_DIR = GENIMG_HOME / "grids"


def make_id(prompt: str, model_id: str) -> str:
  """Stable, sortable id: YYYYMMDD_HHMMSS_<6 hex>. Collision-free via random suffix."""
  ts = datetime.now().strftime("%Y%m%d_%H%M%S")
  digest = hashlib.sha256(f"{prompt}|{model_id}|{secrets.token_hex(4)}".encode()).hexdigest()[:6]
  return f"{ts}_{digest}"


def auto_output_path(gen_id: str, suffix: str = ".png") -> Path:
  """Path under ~/.genimg/generations/ when user doesn't pass -o."""
  GEN_DIR.mkdir(parents=True, exist_ok=True)
  return GEN_DIR / f"{gen_id}{suffix}"


def auto_grid_path(gen_id: str) -> Path:
  GRID_DIR.mkdir(parents=True, exist_ok=True)
  return GRID_DIR / f"{gen_id}.html"


def embed_into_images(meta: dict[str, Any]) -> None:
  """Write prompt + generation params into each PNG output as tEXt chunks.

  Travels with the file even when separated from the sidecar JSON. PNG is
  lossless so the re-save introduces no quality loss, but Pillow drops chunks
  it doesn't model — notably C2PA content credentials (caBX) that some
  providers embed. Accepted trade-off: the sidecar JSON is the provenance of
  record. Non-PNG or unreadable outputs are skipped silently — embedding is
  provenance, never load-bearing.
  """
  params = {k: meta.get(k) for k in ("n", "quality", "resolution", "aspect_ratio", "thinking_level")}
  params = {k: v for k, v in params.items() if v is not None}
  fields = {
    "prompt": meta.get("prompt"),
    "genimg.model": meta.get("model_id"),
    "genimg.provider": meta.get("provider"),
    "genimg.id": meta.get("id"),
    "genimg.params": json.dumps(params) if params else None,
    # A1111-style aggregate key that other tools commonly read.
    "parameters": meta.get("prompt"),
  }
  fields = {k: v for k, v in fields.items() if v}
  for out in meta.get("outputs", []):
    path = Path(out["path"]) if isinstance(out, dict) else Path(out)
    if path.suffix.lower() != ".png" or not path.exists():
      continue
    out_fields = dict(fields)
    if isinstance(out, dict) and out.get("prompt_effective"):
      # Diverse mode: this image was generated from its own perturbed prompt.
      out_fields["prompt"] = out["prompt_effective"]
      out_fields["parameters"] = out["prompt_effective"]
      if out.get("prompt_delta"):
        out_fields["genimg.prompt_delta"] = out["prompt_delta"]
    try:
      with Image.open(path) as img:
        img.load()
        info = PngInfo()
        # Preserve any pre-existing text chunks (provider metadata, ICC text,
        # timestamps); genimg keys take precedence on collision.
        for key, value in getattr(img, "text", {}).items():
          if key not in out_fields:
            info.add_text(key, value)
        for key, value in out_fields.items():
          info.add_text(key, str(value))
        img.save(path, pnginfo=info)
    except Exception:
      continue


def save(meta: dict[str, Any], gen_id: str) -> Path:
  META_DIR.mkdir(parents=True, exist_ok=True)
  path = META_DIR / f"{gen_id}.json"
  path.write_text(json.dumps(meta, indent=2, default=str))
  return path


def build(*, gen_id: str, prompt: str, alias: str, spec, paths: list[Path],
          n: int, cost_usd: float, input: Path | None = None, refs: list[Path] | None = None,
          resolution: str | None = None, aspect_ratio: str | None = None,
          quality: str | None = None, thinking_level: str | None = None,
          grid_path: Path | None = None,
          prompt_deltas: list[str | None] | None = None,
          mode: str | None = None, diverse: bool = False) -> dict[str, Any]:
  from . import diversify

  def _output_entry(i: int, p: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": str(p), "format": p.suffix.lstrip("."), "bytes": p.stat().st_size}
    if prompt_deltas is not None:
      entry["prompt_delta"] = prompt_deltas[i]
      entry["prompt_effective"] = diversify.apply(prompt, prompt_deltas[i])
    return entry

  meta = {
    "id": gen_id,
    "time": datetime.now().astimezone().isoformat(timespec="seconds"),
    "prompt": prompt,
    "alias": alias,
    "model_id": spec.model_id,
    "provider": spec.provider,
    "region": spec.region,
    "n": n,
    "resolution": resolution,
    "aspect_ratio": aspect_ratio,
    "quality": quality,
    "thinking_level": thinking_level,
    "input": str(input) if input else None,
    "refs": [str(r) for r in (refs or [])],
    "mode": mode or "auto",
    "diverse": diverse or prompt_deltas is not None,
    "outputs": [_output_entry(i, p) for i, p in enumerate(paths)],
    "cost_usd_estimated": round(cost_usd, 4),
    "workdir": str(Path.cwd()),
  }
  if grid_path is not None:
    meta["grid"] = {
      "path": str(grid_path),
      "format": grid_path.suffix.lstrip("."),
      "bytes": grid_path.stat().st_size,
    }
  return meta
