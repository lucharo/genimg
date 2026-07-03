from __future__ import annotations

import unittest

from genimg import cost


class CostEstimateTests(unittest.TestCase):
  def test_openai_defaults_to_medium(self) -> None:
    self.assertAlmostEqual(cost.estimate(provider="openai", model_id="gpt-image-2", n=1), 0.053)

  def test_openai_quality_and_n_scale(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", n=2, quality="high"), 2 * 0.211
    )

  def test_openai_resolution_multiplier(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", n=1, quality="low", resolution="4K"),
      0.006 * 6.0,
    )

  def test_google_flat_per_image(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="google", model_id="imagen-4.0-generate-001", n=3), 3 * 0.04
    )

  def test_google_resolution_keyed(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="google", model_id="gemini-3-pro-image-preview", n=1, resolution="2K"),
      0.13,
    )

  def test_unknown_returns_zero(self) -> None:
    self.assertEqual(cost.estimate(provider="openai", model_id="nope", n=1), 0.0)
    self.assertEqual(cost.estimate(provider="google", model_id="nope", n=1), 0.0)
    self.assertEqual(cost.estimate(provider="mystery", model_id="x", n=1), 0.0)


if __name__ == "__main__":
  unittest.main()
