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
  lossless so the re-save introduces no quality loss. Non-PNG or unreadable
  outputs are skipped silently — embedding is provenance, never load-bearing.
  """
  params = {k: meta.get(k) for k in ("n", "quality", "resolution", "aspect_ratio")}
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
    try:
      with Image.open(path) as img:
        img.load()
        info = PngInfo()
        for key, value in fields.items():
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
          quality: str | None = None, grid_path: Path | None = None) -> dict[str, Any]:
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
    "input": str(input) if input else None,
    "refs": [str(r) for r in (refs or [])],
    "outputs": [{"path": str(p), "format": p.suffix.lstrip("."), "bytes": p.stat().st_size} for p in paths],
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
