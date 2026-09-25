from __future__ import annotations

import unittest

from genimg import cost
from genimg.providers import openai as oai

# Measured 2026-09-19 against api.openai.com (`usage.output_tokens_details.image_tokens`);
# each also matches OpenAI's calculator script read on 2026-09-24.
MEASURED_TOKENS = [
  ("gpt-image-2", 1536, 864, "low", 120),
  ("gpt-image-2.5-sunburst", 1536, 864, "medium", 280),
  ("gpt-image-2", 1536, 864, "medium", 1078),
  ("gpt-image-2.5-flare", 1536, 864, "high", 1078),
  ("gpt-image-2", 1024, 1024, "low", 196),
  ("gpt-image-2.5-sunburst", 1024, 1024, "medium", 439),
  ("gpt-image-2.5-sunburst", 1024, 1024, "high", 1756),
  ("gpt-image-2", 1024, 1024, "medium", 1756),
]


class OpenAITokenTests(unittest.TestCase):
  def test_measured_token_counts(self) -> None:
    for model, width, height, quality, expected in MEASURED_TOKENS:
      with self.subTest(model=model, size=f"{width}x{height}", quality=quality):
        self.assertEqual(
          oai.output_tokens(model, width=width, height=height, quality=quality),
          expected,
        )

  def test_half_short_edge_rounds_to_even(self) -> None:
    # 24 / (16/9) = 13.5 → 14 (odd floor rounds up); 16 / (32/9) = 4.5 → 4 (even floor stays).
    self.assertEqual(oai.output_tokens("gpt-image-2.5-sunburst", width=1536, height=864, quality="medium"), 280)
    self.assertEqual(oai.output_tokens("gpt-image-2", width=2048, height=576, quality="low"), 51)

  def test_portrait_counts_like_landscape(self) -> None:
    landscape = oai.output_tokens("gpt-image-2", width=2048, height=1152, quality="medium")
    portrait = oai.output_tokens("gpt-image-2", width=1152, height=2048, quality="medium")
    self.assertEqual((landscape, portrait), (1413, 1413))

  def test_dated_snapshots_and_auto(self) -> None:
    self.assertEqual(oai.token_family("gpt-image-2.5-flare-2026-09-08"), "gpt-image-2.5")
    self.assertEqual(oai.token_family("gpt-image-1.5"), None)
    self.assertEqual(
      oai.output_tokens("gpt-image-2.5-flare-2026-09-08", width=1024, height=1024, quality="auto"),
      439,
    )

  def test_quality_outside_the_grid_is_unpriced(self) -> None:
    self.assertIsNone(oai.output_tokens("gpt-image-2", width=1024, height=1024, quality="max"))
    self.assertIsNone(oai.price_at("gpt-image-2", width=1024, height=1024, quality="max"))


class CostEstimateTests(unittest.TestCase):
  def test_openai_defaults_to_medium_square_1k(self) -> None:
    # 1756 tokens at $30/M.
    self.assertAlmostEqual(cost.estimate(provider="openai", model_id="gpt-image-2", n=1), 0.05268)

  def test_openai_quality_and_n_scale(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", n=2, quality="high"), 2 * 7024 * 30 / 1e6
    )

  def test_openai_prices_the_resolved_size(self) -> None:
    # 2048x1152 medium: 1413 tokens = $0.0424, not the old 2.5x multiplier's $0.1325.
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", quality="medium", resolution="2K", aspect_ratio="16:9"),
      0.04239,
    )
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", quality="high", resolution="2K", aspect_ratio="16:9"),
      0.1695,
    )
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2", quality="low", resolution="4K"),
      oai.output_tokens("gpt-image-2", width=2880, height=2880, quality="low") * 30 / 1e6,
    )

  def test_gpt_image_25_is_priced_by_its_own_grid(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2.5-sunburst", quality="medium", resolution="2K", aspect_ratio="16:9"),
      oai.output_tokens("gpt-image-2.5-sunburst", width=2048, height=1152, quality="medium") * 30 / 1e6,
    )
    self.assertAlmostEqual(
      cost.estimate(provider="openai", model_id="gpt-image-2.5-flare", quality="max"),
      cost.estimate(provider="openai", model_id="gpt-image-2", quality="high"),
    )

  def test_unsupported_size_combo_is_unpriced(self) -> None:
    self.assertIsNone(cost.estimate(provider="openai", model_id="gpt-image-2", resolution="1K", aspect_ratio="16:9"))

  def test_legacy_models_use_the_documented_table(self) -> None:
    self.assertAlmostEqual(cost.estimate(provider="openai", model_id="gpt-image-1.5", quality="high"), 0.133)
    self.assertAlmostEqual(cost.estimate(provider="openai", model_id="gpt-image-1-mini"), 0.011)
    self.assertAlmostEqual(
      oai.price_at("gpt-image-1", width=1536, height=1024, quality="low"), 0.016
    )
    # Undocumented output sizes (a Codex image's real dimensions) scale the square row by area.
    self.assertAlmostEqual(oai.price_at("gpt-image-1.5", width=2048, height=2048), 0.034 * 4)
    # A requested size the model cannot produce has no price.
    self.assertIsNone(cost.estimate(provider="openai", model_id="gpt-image-1.5", resolution="2K"))

  def test_google_resolution_keyed(self) -> None:
    self.assertAlmostEqual(
      cost.estimate(provider="google", model_id="gemini-3-pro-image", n=1, resolution="2K"),
      0.134,
    )

  def test_ga_and_preview_ids_price_identically(self) -> None:
    # Saved metadata may still contain the retired preview id; price it like the stable id.
    ga = cost.estimate(provider="google", model_id="gemini-3.1-flash-image", n=1)
    preview = cost.estimate(provider="google", model_id="gemini-3.1-flash-image-preview", n=1)
    self.assertAlmostEqual(ga, 0.067)
    self.assertAlmostEqual(ga, preview)

  def test_unknown_returns_none(self) -> None:
    self.assertIsNone(cost.estimate(provider="openai", model_id="nope", n=1))
    self.assertIsNone(cost.estimate(provider="google", model_id="nope", n=1))
    self.assertIsNone(cost.estimate(provider="mystery", model_id="x", n=1))


class PriceTableTests(unittest.TestCase):
  def test_openai_table_carries_aspect_keys_where_size_changes_the_price(self) -> None:
    from genimg import providers
    table = providers.get("openai").price_table("gpt-image-2")
    self.assertAlmostEqual(table["medium"]["2K"], 0.10704)          # 2048x2048, the default aspect
    self.assertAlmostEqual(table["medium"]["2K|16:9"], 0.04239)     # 2048x1152
    self.assertNotIn("2K|1:1", table["medium"])
    self.assertNotIn("max", table)


class ApiEquivalentTests(unittest.TestCase):
  def test_openai_output_is_priced_at_its_real_dimensions(self) -> None:
    value = cost.api_equivalent(provider="openai", model_id="gpt-image-2", quality="medium",
                                output={"dimensions": {"width": 1536, "height": 864}})
    self.assertAlmostEqual(value["usd_min"], 1078 * 30 / 1e6)
    self.assertEqual(value["usd_min"], value["usd_max"])

  def test_openai_output_outside_api_sizes_prices_the_request(self) -> None:
    # A thumbnail or test fixture was not generated at that size; fall back to the settings.
    value = cost.api_equivalent(provider="openai", model_id="gpt-image-2", quality="medium",
                                output={"dimensions": {"width": 4, "height": 4}})
    self.assertAlmostEqual(value["usd_min"], 0.05268)

  def test_codex_inferred_gpt_image_2_spans_low_to_high(self) -> None:
    manifest = {"assertions": [{"label": "c2pa.actions", "data": {"actions": [
      {"action": "c2pa.created", "softwareAgent": {"name": "gpt-image", "version": "2.0"}}]}}]}
    output = {"dimensions": {"width": 1024, "height": 1024}, "provenance": {"manifest": manifest}}
    value = cost.api_equivalent(provider="codex", model_id="codex", output=output)
    self.assertEqual((value["model_id"], value["usd_min"], value["usd_max"]), ("gpt-image-2", 0.00588, 0.21072))


if __name__ == "__main__":
  unittest.main()
