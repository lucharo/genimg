# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.9", "genimg"]
#
# [tool.uv.sources]
# genimg = { path = "..", editable = true }
# ///
"""Draw the charts on docs/reference/choosing-a-model.md from scripts/model_benchmarks.csv.

    uv run scripts/model_charts.py

Writes a light and a dark SVG per chart to docs/assets/charts/ and prints the page's
numbers table. Quality and generation time come from the CSV (each row names its source
and date). Cost comes from genimg's own price table at 1024x1024, at the quality setting
the benchmark scored, so every point pairs a score with the price of that same setting.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

from genimg import registry  # noqa: E402
from genimg.providers import get as provider  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "model_benchmarks.csv"
OUT = ROOT / "docs" / "assets" / "charts"

# Colours from the dataviz reference palette (slots 1 and 2), validated for both page
# surfaces. Shape carries the provider too, and every point is labelled, so colour is
# never the only cue.
THEMES = {
  "light": {"surface": "#fbf7ee", "ink": "#1c1917", "ink2": "#52514e", "muted": "#6f6d67",
            "grid": "#e6e1d6", "axis": "#c3c2b7", "google": "#2a78d6", "openai": "#eb6834"},
  "dark":  {"surface": "#1c1917", "ink": "#f5efe6", "ink2": "#c3c2b7", "muted": "#9a988f",
            "grid": "#2e2a27", "axis": "#4a4540", "google": "#3987e5", "openai": "#d95926"},
}
MARKER = {"google": "o", "openai": "s"}
PROVIDER_NAME = {"google": "Google", "openai": "OpenAI"}


@dataclass
class Model:
  alias: str
  provider: str
  setting: str = ""
  elo: float | None = None
  seconds: float | None = None
  arena: float | None = None
  arena_rank: str = ""
  aa_rank: str = ""
  cost: float | None = None
  notes: dict[str, str] = field(default_factory=dict)


def load() -> dict[str, Model]:
  models: dict[str, Model] = {}
  with DATA.open() as fh:
    for row in csv.DictReader(fh):
      alias = row["alias"]
      _, spec = registry.resolve(alias)
      m = models.setdefault(alias, Model(alias, spec.provider))
      value = float(row["value"]) if row["value"] else None
      if row["note"]:
        m.notes[row["metric"]] = row["note"]
      if row["metric"] == "aa_elo":
        m.elo, m.setting, m.aa_rank = value, row["setting"], row["rank"]
        quality = row["setting"] or None
        m.cost = provider(spec.provider).price(spec.model_id, quality, "1K", "1:1")
      elif row["metric"] == "aa_seconds":
        m.seconds = value
      elif row["metric"] == "arena_score":
        m.arena, m.arena_rank = value, row["rank"]
  return models


def frontier(points: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
  """Points no other point beats on both axes (lower x, higher y)."""
  best, keep = float("-inf"), []
  for x, y, name in sorted(points, key=lambda p: (p[0], -p[1])):
    if y > best:
      keep.append((x, y, name))
      best = y
  return keep


@dataclass
class Chart:
  slug: str
  xlabel: str
  xticks: list[float]
  xfmt: str
  xlim: tuple[float, float]
  ylim: tuple[float, float]
  source: str
  # alias -> (dx, dy) offset in points for its label; "ha" follows the sign of dx.
  labels: dict[str, tuple[float, float]]


def label(m: Model) -> str:
  return f"{m.alias} · {m.setting}" if m.setting else m.alias


def draw(chart: Chart, rows: list[tuple[float, float, Model]], theme: str) -> Path:
  t = THEMES[theme]
  plt.rcParams.update({
    "font.family": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 10,
    "svg.fonttype": "path", "svg.hashsalt": "genimg-model-charts",
  })
  fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=100)
  fig.patch.set_alpha(0)
  ax.set_facecolor("none")
  ax.set_xscale("log")
  ax.set_xlim(*chart.xlim)
  ax.set_ylim(*chart.ylim)
  ax.xaxis.set_major_locator(FixedLocator(chart.xticks))
  ax.xaxis.set_minor_locator(NullLocator())
  ax.set_xticklabels([chart.xfmt.format(v) for v in chart.xticks])
  ax.grid(True, color=t["grid"], linewidth=0.8)
  ax.set_axisbelow(True)
  for side in ("top", "right"):
    ax.spines[side].set_visible(False)
  for side in ("left", "bottom"):
    ax.spines[side].set_color(t["axis"])
  ax.tick_params(colors=t["muted"], length=0, pad=6)
  ax.set_xlabel(chart.xlabel, color=t["ink2"], labelpad=8)
  ax.set_ylabel("Quality (Artificial Analysis Elo)", color=t["ink2"], labelpad=8)

  front = frontier([(x, y, m.alias) for x, y, m in rows])
  on_front = {name for _, _, name in front}
  fx = [p[0] for p in front] + [chart.xlim[1]]
  fy = [p[1] for p in front] + [front[-1][1]]
  ax.step(fx, fy, where="post", color=t["ink2"], linewidth=1.5, alpha=0.55, zorder=2,
          solid_joinstyle="round")

  for x, y, m in rows:
    ax.scatter([x], [y], s=78, marker=MARKER[m.provider], color=t[m.provider],
               edgecolors=t["surface"], linewidths=2, zorder=3)
    dx, dy = chart.labels.get(m.alias, (8, 0))
    lead = (dx * dx + dy * dy) ** 0.5 > 16
    ax.annotate(
      label(m), (x, y), xytext=(dx, dy), textcoords="offset points",
      ha="left" if dx >= 0 else "right", va="center", fontsize=9.5,
      color=t["ink"] if m.alias in on_front else t["ink2"],
      fontweight="semibold" if m.alias in on_front else "normal", zorder=4,
      arrowprops={"arrowstyle": "-", "color": t["muted"], "linewidth": 0.8,
                  "shrinkA": 1, "shrinkB": 5} if lead else None,
    )

  handles = [
    Line2D([], [], marker=MARKER[p], linestyle="none", markersize=8, color=t[p],
           markeredgecolor=t["surface"], label=PROVIDER_NAME[p]) for p in ("google", "openai")
  ] + [Line2D([], [], color=t["ink2"], alpha=0.55, linewidth=1.5,
              label="Best for the price (Pareto frontier)" if chart.slug == "cost-quality"
              else "Fastest for the quality (Pareto frontier)")]
  leg = ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9,
                  labelcolor=t["ink2"], handletextpad=0.5, borderaxespad=0.3)
  leg.set_zorder(5)
  ax.text(0.0, 1.03, "Better: up and to the left", transform=ax.transAxes, fontsize=9,
          color=t["muted"], ha="left", va="bottom")
  fig.text(0.01, 0.01, chart.source, fontsize=7.5, color=t["muted"], ha="left", va="bottom")
  fig.tight_layout(rect=(0, 0.04, 1, 1))
  OUT.mkdir(parents=True, exist_ok=True)
  path = OUT / f"{chart.slug}-{theme}.svg"
  fig.savefig(path, format="svg", transparent=True, metadata={"Date": None})
  plt.close(fig)
  return path


def table(models: dict[str, Model]) -> str:
  lines = ["| Model | `-q` | Cost | Time | Artificial Analysis | Arena |",
           "| --- | --- | ---: | ---: | ---: | ---: |"]
  for m in sorted(models.values(), key=lambda m: -(m.elo or 0)):
    cost = f"${m.cost:.3f}" if m.cost is not None else "n/a"
    secs = f"{m.seconds:.0f} s" if m.seconds is not None else "n/a"
    arena = f"{m.arena:.0f} (#{m.arena_rank})" if m.arena is not None else "n/a"
    lines.append(f"| `{m.alias}` | {m.setting} | {cost} | {secs} | "
                 f"{m.elo:.0f} (#{m.aa_rank}) | {arena} |")
  return "\n".join(lines)


def main() -> None:
  models = load()
  as_of = "25 Sep 2026"
  cost = Chart(
    slug="cost-quality", xlabel="Cost per image, 1024×1024, at the benchmarked setting (log scale)",
    xticks=[0.01, 0.02, 0.05, 0.1, 0.2], xfmt="${:g}", xlim=(0.008, 0.36), ylim=(890, 1225),
    source=f"Quality: Artificial Analysis text-to-image leaderboard, {as_of}. Cost: genimg price table.",
    labels={
      "oai:gi1-mini": (4, 13), "gdm:nb2-lite": (-9, 6), "gdm:nb2": (-9, 8),
      "oai:gi1.5": (-16, -18), "gdm:nbp": (14, -18), "oai:gi1": (9, 0),
      "oai:gi2.5": (-18, 16), "oai:gi2.5-flare": (-18, -6), "oai:gi2": (-18, -18),
    },
  )
  speed = Chart(
    slug="speed-quality", xlabel="Median generation time in seconds (log scale)",
    xticks=[2, 5, 10, 20, 50, 100], xfmt="{:g} s", xlim=(2, 220), ylim=(1075, 1215),
    source=f"Quality and time: Artificial Analysis, {as_of}; time is the median of the last 3 days.",
    labels={
      "gdm:nb2-lite": (9, -6), "gdm:nb2": (9, 6), "gdm:nbp": (9, -6), "oai:gi1.5": (9, 6),
      "oai:gi2.5-flare": (-10, 6), "oai:gi2.5": (-10, 7), "oai:gi2": (-10, -8),
    },
  )
  cost_rows = [(m.cost, m.elo, m) for m in models.values() if m.cost and m.elo]
  speed_rows = [(m.seconds, m.elo, m) for m in models.values() if m.seconds and m.elo]
  for theme in THEMES:
    for chart, rows in ((cost, cost_rows), (speed, speed_rows)):
      print("wrote", draw(chart, rows, theme).relative_to(ROOT))
  left_out = sorted(m.alias for m in models.values() if not m.seconds)
  print("speed chart leaves out:", ", ".join(left_out))
  print()
  print(table(models))


if __name__ == "__main__":
  main()
