from __future__ import annotations

import hashlib
import json
import struct
import zlib
from unittest.mock import MagicMock

import c2pa
import pytest
from PIL import Image
from typer.testing import CliRunner

from genimg import cli, cost, history, metadata, registry
from genimg.interfaces import GenerateResult


@pytest.fixture
def credentialled_png(tmp_path):
  """A real PNG with an opaque credential chunk; SDK parsing is external I/O."""
  path = tmp_path / "native.png"
  Image.new("RGB", (1024, 1024), "white").save(path)
  payload = b"caBXtest credential"
  chunk = struct.pack(">I", len(payload) - 4) + payload + struct.pack(">I", zlib.crc32(payload))
  original = path.read_bytes()
  path.write_bytes(original[:33] + chunk + original[33:])
  return path


@pytest.fixture
def sdk(monkeypatch):
  manifest = {
    "claim_generator_info": [{"name": "OpenAI Media Service API"}],
    "assertions": [{"label": "c2pa.actions.v2", "data": {"actions": [
      {"action": "c2pa.created", "softwareAgent": {"name": "gpt-image", "version": "2.0"}},
      {"action": "c2pa.watermarked.unbound"},
    ]}}],
    "signature_info": {"common_name": "OpenAI Media Service"},
  }
  document = {"active_manifest": "active", "manifests": {
    "ingredient": {"assertions": []}, "active": manifest,
  }}
  reader = MagicMock()
  reader.return_value.__enter__.return_value.json.side_effect = lambda: json.dumps(document)
  monkeypatch.setattr(c2pa, "Reader", reader)
  return document, reader


def test_generation_preserves_credentials_and_records_observed_model(credentialled_png, sdk, monkeypatch, tmp_path):
  original = credentialled_png.read_bytes()
  monkeypatch.setattr(metadata, "META_DIR", tmp_path / "meta")
  monkeypatch.setattr(cli.config, "load", lambda: {})
  monkeypatch.setattr(cli, "run_generate", lambda *a, **kw: GenerateResult(
    paths=[credentialled_png], model_used="codex:image"))

  result = CliRunner().invoke(cli._app, ["a cube", "-m", "codex:image", "-o", str(credentialled_png)])

  assert result.exit_code == 0, result.output
  assert credentialled_png.read_bytes() == original
  meta = history.load()[0][0]
  output = meta["outputs"][0]
  assert output["sha256"] == hashlib.sha256(original).hexdigest()
  assert output["dimensions"] == {"width": 1024, "height": 1024}
  assert output["provenance"]["manifest"] == sdk[0]["manifests"]["active"]
  assert output["provenance"]["verification"] == "not_performed"
  assert meta["billing"] == "subscription"
  assert meta["cost_usd_estimated"] is None
  assert meta["api_equivalent_cost"]["usd_min"] == 0.006
  assert meta["api_equivalent_cost"]["usd_max"] == 0.211
  assert "API equivalent" in result.output
  assert history.total_spent() == (0.0, 0)


def test_record_calls_no_generation_and_archives_original(credentialled_png, sdk, monkeypatch, tmp_path):
  monkeypatch.setattr(metadata, "META_DIR", tmp_path / "meta")
  monkeypatch.setattr(metadata, "GEN_DIR", tmp_path / "generations")
  generation = MagicMock(side_effect=AssertionError("record must not generate"))
  monkeypatch.setattr(cli, "run_generate", generation)
  original = credentialled_png.read_bytes()

  result = CliRunner().invoke(cli._app, ["record", str(credentialled_png), "--prompt", "a cube",
    "-m", "codex:image", "--billing", "subscription"])

  assert result.exit_code == 0, result.output
  generation.assert_not_called()
  meta = history.load()[0][0]
  from pathlib import Path
  archived = Path(meta["outputs"][0]["path"])
  assert archived.parent == metadata.GEN_DIR
  assert archived.read_bytes() == original == credentialled_png.read_bytes()
  assert meta["recorded_from"] == str(credentialled_png)
  assert meta["billing_source"] == "user_declared"
  assert meta["api_equivalent_cost"]["priced_images"] == 1


@pytest.mark.parametrize("failure", ["invalid", "existing", "billing"])
def test_record_rejects_invalid_input_before_writing(tmp_path, monkeypatch, failure):
  source = tmp_path / "source.png"
  output = tmp_path / "out.png"
  Image.new("RGB", (4, 4)).save(source)
  if failure == "invalid":
    source.write_bytes(b"not a PNG")
  if failure == "existing":
    output.write_bytes(b"keep me")
  monkeypatch.setattr(metadata, "META_DIR", tmp_path / "meta")
  result = CliRunner().invoke(cli._app, ["record", str(source), "--prompt", "a cube",
    "-m", "codex:image", "--billing", "invalid" if failure == "billing" else "subscription", "-o", str(output)])
  assert result.exit_code != 0
  assert not metadata.META_DIR.exists()
  assert output.read_bytes() == b"keep me" if failure == "existing" else not output.exists()


def test_unreadable_credentials_are_kept_and_not_priced(credentialled_png):
  original = credentialled_png.read_bytes()
  meta = metadata.build(gen_id="broken", prompt="cube", alias="codex:image",
    spec=registry.resolve("codex:image")[1], paths=[credentialled_png], n=1, cost_usd=None)
  metadata.embed_into_images(meta)
  assert credentialled_png.read_bytes() == original
  assert meta["outputs"][0]["provenance"]["status"] == "unreadable"
  assert meta["api_equivalent_cost"]["usd_min"] is None


def test_missing_credentials_remain_unknown_and_unsigned_hash_matches(tmp_path):
  path = tmp_path / "plain.png"
  Image.new("RGB", (4, 4)).save(path)
  meta = metadata.build(gen_id="plain", prompt="cube", alias="codex:image",
    spec=registry.resolve("codex:image")[1], paths=[path], n=1, cost_usd=None)
  metadata.embed_into_images(meta)
  assert meta["outputs"][0]["provenance"]["status"] == "absent"
  assert meta["outputs"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
  assert meta["api_equivalent_cost"]["usd_max"] is None


def test_unknown_generator_is_not_substituted_with_documented_default(credentialled_png, sdk):
  sdk[0]["manifests"]["active"]["assertions"][0]["data"]["actions"][0]["softwareAgent"]["version"] = "2.5"
  meta = metadata.build(gen_id="unknown", prompt="cube", alias="codex:image",
    spec=registry.resolve("codex:image")[1], paths=[credentialled_png], n=1, cost_usd=None)
  assert meta["api_equivalent_cost"]["usd_min"] is None
  assert meta["outputs"][0]["api_equivalent_cost"]["model_id"] is None


def test_partial_generation_estimate_counts_delivered_outputs(tmp_path):
  path = tmp_path / "image.png"
  Image.new("RGB", (4, 4)).save(path)
  meta = metadata.build(gen_id="partial", prompt="cube", alias="oai:gi2",
    spec=registry.resolve("oai:gi2")[1], paths=[path], n=3, cost_usd=0.159)
  assert meta["billing"] == "api"
  assert meta["api_equivalent_cost"] == {
    "usd_min": 0.053, "usd_max": 0.053, "priced_images": 1, "images": 1,
  }


def test_partial_unknown_cost_never_looks_like_complete_range():
  assert cost.sum_equivalents([{"usd_min": 0.01, "usd_max": 0.02}, {"usd_min": None, "usd_max": None}]) == {
    "usd_min": None, "usd_max": None, "priced_images": 1, "images": 2,
  }
