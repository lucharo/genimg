"""Curated prompt deltas for `-d/--diverse` (issue #9).

Plain `-n` samples the same prompt N times and converges on near-duplicates
for simple subjects. Diverse mode appends a distinct style/composition delta
to each generation instead. The pool is a fixed curated list; reproducibility
comes from recording each generation's delta in the metadata sidecar, not
from a fixed pick order.

Design invariant: genimg never calls a text LLM — only image generation
models. Tailored (non-curated) diversity is the caller's job: an agent
driving the CLI is itself an LLM and can compose its own prompt variants.
Do not add an LLM-expansion strategy here.

Generation #1 always keeps the base prompt untouched, so every diverse batch
contains one un-perturbed anchor to judge the deltas against.
"""
from __future__ import annotations

import random

# Mix of style, palette, lighting, and composition levers. Must hold at least
# MAX_N - 1 entries (CLI caps -n at 10; index 0 is the base prompt).
DELTAS: list[str] = [
  "flat minimal vector style, generous negative space",
  "isometric 3D perspective",
  "hand-drawn ink sketch, loose expressive linework",
  "bold geometric abstraction from simple primitive shapes",
  "high-contrast dramatic lighting, deep shadows",
  "soft pastel palette, light airy composition",
  "retro screen-print poster style, limited flat palette",
  "photorealistic rendering, shallow depth of field",
  "dark background with a neon accent glow",
  "watercolor wash textures, organic edges",
  "extreme close-up framing on the defining detail",
  "off-center composition with a strong diagonal",
]


def pick_deltas(n: int, rng: random.Random | None = None) -> list[str | None]:
  """One delta per generation: [None, d1, ..., d(n-1)], sampled without replacement."""
  if n - 1 > len(DELTAS):
    raise ValueError(f"diverse mode supports at most n={len(DELTAS) + 1}, got n={n}")
  picks = (rng or random).sample(DELTAS, n - 1)
  return [None, *picks]


def apply(prompt: str, delta: str | None) -> str:
  """Effective prompt for one generation: base prompt, or base + appended delta."""
  return prompt if delta is None else f"{prompt} — {delta}"
