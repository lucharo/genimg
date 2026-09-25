from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from typer.testing import CliRunner

from genimg import (
  cli,
  cost,
  discovery,
  draw,
  grid,
  history,
  metadata,
  providers,
  registry,
)
from genimg.auth.base import AuthInfo
from genimg.generate import generate
from genimg.interfaces import GenerateRequest
from genimg.providers import openai


@pytest.mark.parametrize("name,variant", [
  ("oai:gi2.5", "sunburst"),
  ("oai:gi2.5-flare", "flare"),
  ("oai:gpt-image-2.5-sunburst", "sunburst"),
  ("oai:gpt-image-2.5-flare", "flare"),
  ("gpt-image-2.5-sunburst", "sunburst"),
  ("gpt-image-2.5-flare", "flare"),
])
def test_curated_aliases_resolve(name, variant):
  assert registry.resolve(name) == (
    f"oai:gpt-image-2.5-{variant}",
    registry.ModelSpec("openai", f"gpt-image-2.5-{variant}", quality_rank=10 if variant == "sunburst" else 9),
  )


@pytest.mark.parametrize("alias,variant,quality", [
  ("oai:gi2.5", "sunburst", "max"),
  ("oai:gi2.5-flare", "flare", "xhigh"),
])
@pytest.mark.parametrize("edit", [False, True])
def test_cli_routes_generation_and_edit_to_exact_model(tmp_path, alias, variant, quality, edit):
  image_path = tmp_path / "input.png"
  Image.new("RGB", (16, 16)).save(image_path)
  payload = image_path.read_bytes()
  client = MagicMock()
  response = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(payload).decode())])
  client.images.generate.return_value = response
  client.images.edit.return_value = response
  output = tmp_path / "out.png"
  args = ["a circle", "-m", alias, "-q", quality, "-o", str(output)]
  if edit:
    args += ["-i", str(image_path)]
  with (
    patch.object(openai, "get_client", return_value=client),
    patch.object(cli.config, "load", return_value={}),
    patch.object(metadata, "META_DIR", tmp_path / "meta"),
    patch.object(metadata, "make_id", return_value="test-25"),
  ):
    result = CliRunner().invoke(cli._app, args)
  assert result.exit_code == 0, result.output
  api = client.images.edit if edit else client.images.generate
  kwargs = dict(api.call_args.kwargs)
  if edit:
    handles = kwargs.pop("image")
    assert [h.name for h in handles] == [str(image_path)]
    assert all(h.closed for h in handles)
    client.images.generate.assert_not_called()
  else:
    client.images.edit.assert_not_called()
  assert kwargs == {"model": f"gpt-image-2.5-{variant}", "prompt": "a circle", "size": "1024x1024", "quality": quality, "n": 1}
  with Image.open(output) as image:
    assert image.size == (16, 16)
  saved = json.loads((tmp_path / "meta" / "test-25.json").read_text())
  # 1024x1024: max = 7024 tokens, xhigh = 3122 tokens at $30/M, saved rounded to 4 places.
  assert saved["cost_usd_estimated"] == {"max": 0.2107, "xhigh": 0.0937}[quality]
  assert saved["model_id"] == f"gpt-image-2.5-{variant}"
  assert f"${saved['cost_usd_estimated']:.4f} (estimate)" in result.output
  assert "unknown (estimate)" not in result.output


@pytest.mark.parametrize("model", ["gpt-image-2", "gpt-image-1.5", "gpt-image-2.5-unknown"])
def test_extended_quality_rejected_before_api_for_other_models(tmp_path, model):
  with patch.object(openai, "get_client", side_effect=AssertionError("must not contact API")):
    result = CliRunner().invoke(cli._app, ["circle", "-m", model, "-q", "max", "--dry-run"])
    assert result.exit_code == 1, result.output
    assert "quality" in result.output
    with pytest.raises(RuntimeError, match="quality"):
      generate(GenerateRequest(prompt="circle", model=model, quality="max", output=tmp_path / "out.png"))


@pytest.mark.parametrize("variant", ["sunburst", "flare"])
def test_snapshot_quality_is_priced_like_its_family(variant):
  model = f"gpt-image-2.5-{variant}-2026-09-08"
  with patch.object(cli.config, "load", return_value={}), \
       patch.object(cli.auth_resolve, "info", return_value=AuthInfo("direct", "env", "-", "OPENAI_API_KEY", True)):
    result = CliRunner().invoke(cli._app, ["circle", "-m", model, "-q", "max", "--dry-run"])
  assert result.exit_code == 0, result.output
  assert "$0.2107" in result.output
  assert cost.estimate(provider="openai", model_id=model, quality="max") == pytest.approx(0.21072)


def test_models_and_studio_discover_both_variants():
  ids = [f"gpt-image-2.5-{v}" for v in ("sunburst", "flare")]
  client = MagicMock()
  client.models.list.return_value = [SimpleNamespace(id=model) for model in ids]
  with patch.object(openai, "get_client", return_value=client):
    probes = providers.get("openai").probe_listed(
      [(a, s) for a, s in registry.all_canonical().items() if s.provider == "openai"])
  with patch.object(discovery, "get_or_probe", return_value=(probes, 0)):
    result = CliRunner().invoke(cli._app, ["models", "--json"])
  assert result.exit_code == 0, result.output
  rows = {row["model_id"]: row for row in json.loads(result.output)}
  studio = {row["modelId"]: row for row in draw._studio_models()}
  for model in ids:
    assert rows[model]["status"] == "listed"
    assert studio[model]["qualityOptions"] == ["low", "medium", "high", "xhigh", "max", "auto"]
  assert studio["gpt-image-2"]["qualityOptions"] == ["low", "medium", "high", "auto"]


def test_unknown_cost_survives_history_and_grid(tmp_path):
  image_path = tmp_path / "image.png"
  Image.new("RGB", (16, 16)).save(image_path)
  entry = {"id": "unknown", "model_id": "gpt-image-2.5-sunburst", "cost_usd_estimated": None,
           "outputs": [{"path": str(image_path)}]}
  (tmp_path / "unknown.json").write_text(json.dumps(entry))
  (tmp_path / "known.json").write_text(json.dumps({"cost_usd_estimated": 0.25}))
  with patch.object(metadata, "META_DIR", tmp_path):
    assert history.total_spent() == (0.25, 1)
    result = CliRunner().invoke(cli._app, ["history"])
    assert result.exit_code == 0, result.output
    assert "unknown" in result.output
  out, total = grid.render([image_path], tmp_path / "grid.html", meta=entry, provider="openai")
  assert total is None
  assert "$0.05" not in out.read_text()
