from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from genimg import discovery
from genimg.interfaces import ProbeResult
from genimg.providers import google as google_provider
from genimg.providers import openai as openai_provider


class DiscoveryCacheTests(unittest.TestCase):
  def test_uses_cache_before_refresh_interval(self) -> None:
    entries = {"oai:gpt-image-2": discovery.ModelSpec("openai", "gpt-image-2")}
    with tempfile.TemporaryDirectory() as td, patch.object(discovery, "CACHE_PATH", Path(td) / "models.json"), \
         patch.object(discovery, "all_canonical", return_value=entries):
      cached_probe = ProbeResult(model="gpt-image-2", status="listed")
      discovery.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
      discovery.CACHE_PATH.write_text(json.dumps({
        "timestamp": time.time() - (discovery.CACHE_REFRESH_INTERVAL_SECONDS - 1),
        "probes": {"oai:gpt-image-2": cached_probe.model_dump()},
      }))

      with patch.object(discovery, "probe_all", side_effect=AssertionError("should not refresh")):
        probes, age = discovery.get_or_probe()

      self.assertGreater(age, 0)
      self.assertEqual(probes["oai:gpt-image-2"].status, "listed")

  def test_refreshes_cache_after_refresh_interval(self) -> None:
    with tempfile.TemporaryDirectory() as td, patch.object(discovery, "CACHE_PATH", Path(td) / "models.json"):
      stale_probe = ProbeResult(model="gpt-image-1.5", status="missing")
      discovery.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
      discovery.CACHE_PATH.write_text(json.dumps({
        "timestamp": time.time() - (discovery.CACHE_REFRESH_INTERVAL_SECONDS + 1),
        "probes": {"oai:gpt-image-1.5": stale_probe.model_dump()},
      }))

      fresh_probe = ProbeResult(model="gpt-image-2", status="listed")
      with patch.object(discovery, "probe_all", return_value={"oai:gpt-image-2": fresh_probe}) as probe_all:
        probes, age = discovery.get_or_probe()

      probe_all.assert_called_once_with()
      self.assertEqual(age, 0.0)
      self.assertEqual(probes["oai:gpt-image-2"].status, "listed")

  def test_auth_failures_are_not_cached_so_new_credentials_are_picked_up(self) -> None:
    entries = {"oai:listed": discovery.ModelSpec("openai", "gpt-image-listed")}
    client = SimpleNamespace(models=SimpleNamespace(list=lambda: [SimpleNamespace(id="gpt-image-listed")]))
    hint = "No openai auth detected. Run `genimg setup` or set OPENAI_API_KEY."
    with tempfile.TemporaryDirectory() as td, patch.object(discovery, "CACHE_PATH", Path(td) / "models.json"), \
         patch.object(discovery, "all_canonical", return_value=entries):
      with patch.object(openai_provider, "get_client", side_effect=RuntimeError(hint)):
        first, _ = discovery.get_or_probe()
      first_saved = json.loads(discovery.CACHE_PATH.read_text())
      with patch.object(openai_provider, "get_client", return_value=client):
        second, _ = discovery.get_or_probe()
      second_saved = json.loads(discovery.CACHE_PATH.read_text())

    self.assertEqual(first["oai:listed"], ProbeResult(model="gpt-image-listed", status="auth", detail=hint))
    self.assertEqual(first_saved["probes"], {})
    self.assertEqual(second["oai:listed"].status, "listed")
    self.assertEqual(second_saved, {"timestamp": first_saved["timestamp"],
                                    "probes": {"oai:listed": second["oai:listed"].model_dump()}})


class DiscoveryProbeTests(unittest.TestCase):
  def test_probe_all_uses_parallel_model_list_checks(self) -> None:
    entries = {
      "gdm:global": discovery.ModelSpec("google", "gemini-listed", region="global"),
      "gdm:regional": discovery.ModelSpec("google", "gemini-regional-image", region="us-central1"),
      "oai:listed": discovery.ModelSpec("openai", "gpt-image-listed"),
      "oai:missing": discovery.ModelSpec("openai", "gpt-image-missing"),
    }
    barrier = threading.Barrier(3)

    class FakeModels:
      def __init__(self, models: list[object]):
        self.models = models

      def list(self) -> list[object]:
        barrier.wait(timeout=2)
        return self.models

    class FakeClient:
      def __init__(self, models: list[object]):
        self.models = FakeModels(models)

    def fake_google_client(region: str = "global", project: str | None = None, profile=None) -> FakeClient:
      if region == "global":
        return FakeClient([{"name": "models/gemini-listed"}])
      return FakeClient([SimpleNamespace(name="publishers/google/models/gemini-regional-image")])

    with (
      patch.object(discovery, "all_canonical", return_value=entries),
      patch.object(openai_provider, "get_client", return_value=FakeClient([SimpleNamespace(id="gpt-image-listed")])),
      patch.object(google_provider, "get_client", side_effect=fake_google_client),
    ):
      probes = discovery.probe_all()

    self.assertEqual(set(probes), set(entries))
    self.assertEqual(probes["gdm:global"].status, "listed")
    self.assertEqual(probes["gdm:regional"].status, "listed")
    self.assertEqual(probes["oai:listed"].status, "listed")
    self.assertEqual(probes["oai:missing"].status, "missing")

  def test_probe_all_rejects_unknown_provider(self) -> None:
    entries = {"bad:model": discovery.ModelSpec("not-a-provider", "test-model")}  # type: ignore[arg-type]

    with patch.object(discovery, "all_canonical", return_value=entries):
      with self.assertRaisesRegex(ValueError, "unknown provider"):
        discovery.probe_all()


if __name__ == "__main__":
  unittest.main()
