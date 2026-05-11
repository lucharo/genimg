from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from genimg import discovery
from genimg.interfaces import ProbeResult


class DiscoveryCacheTests(unittest.TestCase):
  def test_uses_cache_before_refresh_interval(self) -> None:
    with tempfile.TemporaryDirectory() as td, patch.object(discovery, "CACHE_PATH", Path(td) / "models.json"):
      cached_probe = ProbeResult(model="gpt-image-2", status="working")
      discovery.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
      discovery.CACHE_PATH.write_text(json.dumps({
        "timestamp": time.time() - (4 * 24 * 60 * 60),
        "probes": {"oai:gpt-image-2": cached_probe.model_dump()},
      }))

      with patch.object(discovery, "probe_all", side_effect=AssertionError("should not refresh")):
        probes, age = discovery.get_or_probe()

      self.assertGreater(age, 0)
      self.assertEqual(probes["oai:gpt-image-2"].status, "working")

  def test_refreshes_cache_after_refresh_interval(self) -> None:
    with tempfile.TemporaryDirectory() as td, patch.object(discovery, "CACHE_PATH", Path(td) / "models.json"):
      stale_probe = ProbeResult(model="gpt-image-1.5", status="404")
      discovery.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
      discovery.CACHE_PATH.write_text(json.dumps({
        "timestamp": time.time() - (6 * 24 * 60 * 60),
        "probes": {"oai:gpt-image-1.5": stale_probe.model_dump()},
      }))

      fresh_probe = ProbeResult(model="gpt-image-2", status="working")
      with patch.object(discovery, "probe_all", return_value={"oai:gpt-image-2": fresh_probe}) as probe_all:
        probes, age = discovery.get_or_probe()

      probe_all.assert_called_once_with()
      self.assertEqual(age, 0.0)
      self.assertEqual(probes["oai:gpt-image-2"].status, "working")


class DiscoveryProbeTests(unittest.TestCase):
  def test_default_probe_parallelism_covers_current_registry_size(self) -> None:
    entries = {
      f"gdm:test-{i}": discovery.ModelSpec("google", f"test-model-{i}")
      for i in range(10)
    }
    barrier = threading.Barrier(len(entries))

    class FakeGoogle:
      def probe(self, model: str, region: str | None = None) -> ProbeResult:
        barrier.wait(timeout=2)
        return ProbeResult(model=model, status="working")

    class FakeOpenAI:
      def probe(self, model: str, region: str | None = None) -> ProbeResult:
        barrier.wait(timeout=2)
        return ProbeResult(model=model, status="working")

    with (
      patch.object(discovery, "all_canonical", return_value=entries),
      patch.object(discovery, "GeminiImageGen", FakeGoogle),
      patch.object(discovery, "OpenAIImageGen", FakeOpenAI),
    ):
      probes = discovery.probe_all()

    self.assertEqual(set(probes), set(entries))


if __name__ == "__main__":
  unittest.main()
