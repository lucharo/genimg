"""Per-generation metadata sidecar (~/.genimg/metadata/<id>.json).

Records prompt, model, paths, cost, params for searchability + reproducibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from PIL.PngImagePlugin import PngInfo

GENIMG_HOME = Path(os.getenv("GENIMG_HOME") or Path.home() / ".genimg")
GEN_DIR = GENIMG_HOME / "generations"
META_DIR = GENIMG_HOME / "metadata"
GRID_DIR = GENIMG_HOME / "grids"


def _absolute_path(value: str | Path, workdir: Path | None) -> str:
  path = Path(value).expanduser()
  if path.is_absolute():
    return str(path.resolve(strict=False))
  if workdir is None:
    raise ValueError(f"relative metadata path has no absolute workdir: {value}")
  return str((workdir / path).resolve(strict=False))


def normalize_paths(meta: dict[str, Any]) -> dict[str, Any]:
  """Return a copy whose path-bearing fields are absolute.

  Legacy relative paths are resolved against the workdir recorded in their
  sidecar. A relative path without an absolute recorded workdir is ambiguous,
  so callers must treat that record as unreadable rather than guessing.
  """
  out = deepcopy(meta)
  raw_workdir = out.get("workdir")
  workdir = None
  if raw_workdir:
    candidate = Path(raw_workdir).expanduser()
    if not candidate.is_absolute():
      raise ValueError(f"metadata workdir is not absolute: {raw_workdir}")
    workdir = candidate.resolve(strict=False)
    out["workdir"] = str(workdir)

  if out.get("input") is not None:
    out["input"] = _absolute_path(out["input"], workdir)
  out["refs"] = [_absolute_path(path, workdir) for path in out.get("refs", [])]

  outputs = []
  for item in out.get("outputs", []):
    if isinstance(item, dict):
      item = dict(item)
      item["path"] = _absolute_path(item["path"], workdir)
    else:
      item = _absolute_path(item, workdir)
    outputs.append(item)
  out["outputs"] = outputs

  if isinstance(out.get("grid"), dict) and out["grid"].get("path") is not None:
    out["grid"] = dict(out["grid"])
    out["grid"]["path"] = _absolute_path(out["grid"]["path"], workdir)
  return out


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
    "genimg.name": meta.get("name"),
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
          n: int, cost_usd: float | None, input: Path | None = None, refs: list[Path] | None = None,
          resolution: str | None = None, aspect_ratio: str | None = None,
          quality: str | None = None, thinking_level: str | None = None,
          grid_path: Path | None = None,
          prompt_deltas: list[str | None] | None = None,
          mode: str | None = None, diverse: bool = False,
          name: str | None = None) -> dict[str, Any]:
  from . import diversify

  workdir = Path.cwd().resolve(strict=False)

  def _output_entry(i: int, p: Path) -> dict[str, Any]:
    absolute = p.expanduser().resolve(strict=False)
    entry: dict[str, Any] = {
      "path": str(absolute),
      "format": absolute.suffix.lstrip("."),
      "bytes": absolute.stat().st_size,
    }
    if prompt_deltas is not None:
      entry["prompt_delta"] = prompt_deltas[i]
      entry["prompt_effective"] = diversify.apply(prompt, prompt_deltas[i])
    return entry

  meta = {
    "id": gen_id,
    "time": datetime.now().astimezone().isoformat(timespec="seconds"),
    "name": name,
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
    "input": _absolute_path(input, workdir) if input else None,
    "refs": [_absolute_path(r, workdir) for r in (refs or [])],
    "mode": mode or "auto",
    "diverse": diverse or prompt_deltas is not None,
    "outputs": [_output_entry(i, p) for i, p in enumerate(paths)],
    "cost_usd_estimated": round(cost_usd, 4) if cost_usd is not None else None,
    "workdir": str(workdir),
  }
  if spec.provider == "codex":
    meta.update(billing="subscription", model_selection="runtime", aspect_ratio_mode="prompt")
  if grid_path is not None:
    absolute_grid = grid_path.expanduser().resolve(strict=False)
    meta["grid"] = {
      "path": str(absolute_grid),
      "format": absolute_grid.suffix.lstrip("."),
      "bytes": absolute_grid.stat().st_size,
    }
  return meta
