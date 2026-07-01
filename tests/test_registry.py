from __future__ import annotations

import unittest
from unittest.mock import patch

from genimg import registry


class RegistryResolveTests(unittest.TestCase):
  def test_resolve_alias_chain_to_spec(self) -> None:
    alias, spec = registry.resolve("gdm:nano-banana")  # → gdm:nb
    self.assertEqual(alias, "gdm:nb")
    self.assertEqual(spec.model_id, "gemini-2.5-flash-image")
    self.assertEqual(spec.provider, "google")

  def test_resolve_canonical_alias(self) -> None:
    alias, spec = registry.resolve("oai:gpt-image-2")
    self.assertEqual(alias, "oai:gpt-image-2")
    self.assertEqual(spec.provider, "openai")

  def test_resolve_short_alias(self) -> None:
    alias, _ = registry.resolve("oai:gi2")
    self.assertEqual(alias, "oai:gpt-image-2")

  def test_resolve_bare_model_id(self) -> None:
    _, spec = registry.resolve("gpt-image-2")
    self.assertEqual(spec.model_id, "gpt-image-2")
    self.assertEqual(spec.provider, "openai")

  def test_unknown_raises(self) -> None:
    with self.assertRaises(ValueError):
      registry.resolve("nope:nothing")

  def test_pruned_mirrors_removed(self) -> None:
    for bad in ("google:nb2", "openai:gi2", "openai:gpt-image-2", "oai:gi1m"):
      with self.assertRaises(ValueError):
        registry.resolve(bad)

  def test_alias_cycle_detected(self) -> None:
    with patch.dict(registry._REGISTRY, {"x:a": "x:b", "x:b": "x:a"}, clear=False):
      with self.assertRaisesRegex(ValueError, "cycle"):
        registry.resolve("x:a")


class RegistryHelperTests(unittest.TestCase):
  def test_all_canonical_only_specs(self) -> None:
    canon = registry.all_canonical()
    self.assertTrue(all(isinstance(s, registry.ModelSpec) for s in canon.values()))
    self.assertIn("gdm:nb2", canon)
    self.assertNotIn("gdm:nano-banana", canon)  # alias, not a canonical entry

  def test_aliases_for(self) -> None:
    self.assertIn("gdm:nano-banana", registry.aliases_for("gdm:nb"))


if __name__ == "__main__":
  unittest.main()
