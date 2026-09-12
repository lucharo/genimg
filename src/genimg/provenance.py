"""Read embedded C2PA claims offline. Extraction does not establish signature trust."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import c2pa
from PIL import Image


def has_png_credentials(path: Path) -> bool:
  """Recognise caBX even when the credential payload itself cannot be decoded."""
  with path.open("rb") as stream:
    if stream.read(8) != b"\x89PNG\r\n\x1a\n":
      return False
    while header := stream.read(8):
      if len(header) != 8:
        return False
      length, kind = int.from_bytes(header[:4], "big"), header[4:]
      if kind == b"caBX":
        return True
      if kind == b"IEND":
        return False
      stream.seek(length + 4, 1)
  return False


def read(path: Path) -> dict[str, Any]:
  """Keep the SDK-selected active manifest, never substitute an ingredient's claim."""
  # No remote manifests, certificate lookups, or implicit trust declarations.
  # A per-reader context avoids changing another consumer's SDK settings.
  settings = {
    "core": {"allowed_network_hosts": []},
    "verify": {"verify_after_reading": False, "remote_manifest_fetch": False, "ocsp_fetch": False},
  }
  present = has_png_credentials(path)
  try:
    with c2pa.Context.from_dict(settings) as context, c2pa.Reader(path, context=context) as reader:
      document = json.loads(reader.json())
      active = document.get("active_manifest")
      manifest = document.get("manifests", {}).get(active)
      if not isinstance(manifest, dict):
        return {"status": "unreadable" if present else "absent", "verification": "not_performed"}
      return {
        "status": "present", "source": "c2pa", "verification": "not_performed",
        "active_manifest": active, "manifest": manifest,
      }
  except Exception as error:
    # Metadata must not fail a successful image generation. Do not expose raw
    # SDK errors (which may contain URLs or content from an untrusted asset).
    return {"status": "unreadable" if present else "absent", "verification": "not_performed",
            "error_type": type(error).__name__} if present else {
              "status": "absent", "verification": "not_performed"}


def inspect_image(path: Path) -> dict[str, Any]:
  fields: dict[str, Any] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
  try:
    with Image.open(path) as image:
      fields["dimensions"] = {"width": image.width, "height": image.height}
  except (OSError, ValueError):
    pass
  fields["provenance"] = read(path)
  return fields


def generators(output: dict[str, Any]) -> list[dict[str, Any]]:
  """Reported creation agents only; conversion/watermark software is not a model."""
  manifest = output.get("provenance", {}).get("manifest", {})
  agents = []
  for assertion in manifest.get("assertions", []):
    if assertion.get("label") not in ("c2pa.actions", "c2pa.actions.v2"):
      continue
    for action in assertion.get("data", {}).get("actions", []):
      agent = action.get("softwareAgent")
      if action.get("action") == "c2pa.created" and isinstance(agent, dict) and agent not in agents:
        agents.append(agent)
  return agents


def describe(outputs: list[dict[str, Any]]) -> str:
  names = dict.fromkeys(
    " ".join(str(agent[k]) for k in ("name", "version") if agent.get(k))
    for output in outputs if isinstance(output, dict) for agent in generators(output)
  )
  return ", ".join(filter(None, names)) or "unknown"
