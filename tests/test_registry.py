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


class SignatureInferenceTests(unittest.TestCase):
  def test_unregistered_gemini_image_infers_google_global(self) -> None:
    alias, spec = registry.resolve("gemini-9.9-flash-image")  # not in registry
    self.assertEqual(alias, "gemini-9.9-flash-image")
    self.assertEqual(spec.provider, "google")
    self.assertEqual(spec.region, "global")
    self.assertEqual(spec.model_id, "gemini-9.9-flash-image")

  def test_current_gemini_aliases_use_serving_stable_ids(self) -> None:
    self.assertEqual(registry.resolve("gdm:nb2")[1].model_id, "gemini-3.1-flash-image")
    self.assertEqual(registry.resolve("gdm:nbp")[1].model_id, "gemini-3-pro-image")

  def test_unregistered_gpt_image_infers_openai(self) -> None:
    _, spec = registry.resolve("gpt-image-9")
    self.assertEqual(spec.provider, "openai")
    self.assertIsNone(spec.region)

  def test_dalle_not_inferred(self) -> None:
    # dall-e is intentionally excluded: the OpenAI provider only speaks the gpt-image shape.
    with self.assertRaises(ValueError):
      registry.resolve("dall-e-3")

  def test_unregistered_imagen_infers_google_regional(self) -> None:
    _, spec = registry.resolve("imagen-5.0-generate-001")
    self.assertEqual(spec.provider, "google")
    self.assertEqual(spec.region, "us-central1")

  def test_registered_bare_id_keeps_curated_spec(self) -> None:
    # a registered id keeps its curated rank/region, not the inferred rank 0
    _, spec = registry.resolve("gpt-image-2")
    self.assertEqual(spec.quality_rank, 9)

  def test_non_image_and_garbage_still_unknown(self) -> None:
    for bad in ("gemini-2.5-flash", "google:nb2", "nope:nothing", "random", "gdm:typo"):
      with self.assertRaises(ValueError):
        registry.resolve(bad)


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
