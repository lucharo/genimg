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
tables. Quality and generation time come from the CSV (each row names its source, date
and the setting the benchmark scored). Cost comes from genimg's own price table at
1024x1024 for that same setting. One point per (model, setting): when the CSV holds
scores for several settings of one model, a thin line joins them.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
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
  """One model at one setting, as a benchmark scored it."""
  alias: str
  provider: str
  setting: str = ""
  elo: float | None = None
  aa_rank: str = ""
  seconds: float | None = None
  cost: float | None = None


def load() -> tuple[list[Model], dict[str, tuple[float, str]]]:
  """Artificial Analysis points keyed by (alias, setting), and Arena scores by alias."""
  points: dict[tuple[str, str], Model] = {}
  arena: dict[str, tuple[float, str]] = {}
  with DATA.open() as fh:
    for row in csv.DictReader(fh):
      alias, setting = row["alias"], row["setting"]
      value = float(row["value"]) if row["value"] else None
      if row["metric"] == "arena_score":
        if value is not None:
          arena[alias] = (value, row["rank"])
        continue
      _, spec = registry.resolve(alias)
      m = points.get((alias, setting))
      if m is None:
        cost = provider(spec.provider).price(spec.model_id, setting or None, "1K", "1:1")
        m = points[alias, setting] = Model(alias, spec.provider, setting, cost=cost)
      if row["metric"] == "aa_elo":
        m.elo, m.aa_rank = value, row["rank"]
      elif row["metric"] == "aa_seconds":
        m.seconds = value
  return list(points.values()), arena


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
  # (dx, dy) offset in points for a label, keyed "alias" or "alias@setting";
  # "ha" follows the sign of dx.
  labels: dict[str, tuple[float, float]]


def key(m: Model) -> str:
  return f"{m.alias}@{m.setting}"


def label(m: Model, top: bool) -> str:
  """The best-scoring setting carries the model name; its other settings only the setting."""
  if not top:
    return m.setting
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

  front = frontier([(x, y, key(m)) for x, y, m in rows])
  on_front = {name for _, _, name in front}
  fx = [p[0] for p in front] + [chart.xlim[1]]
  fy = [p[1] for p in front] + [front[-1][1]]
  ax.step(fx, fy, where="post", color=t["ink2"], linewidth=1.5, alpha=0.55, zorder=2,
          solid_joinstyle="round")

  by_model: dict[str, list[tuple[float, float, Model]]] = {}
  for row in rows:
    by_model.setdefault(row[2].alias, []).append(row)
  multi = {a: sorted(ps, key=lambda p: p[0]) for a, ps in by_model.items() if len(ps) > 1}
  for ps in multi.values():
    ax.plot([p[0] for p in ps], [p[1] for p in ps], color=t[ps[0][2].provider],
            linewidth=1, alpha=0.7, zorder=2.5, solid_capstyle="round")
  tops = {a: max(ps, key=lambda p: p[1])[2] for a, ps in by_model.items()}

  # Google draws after OpenAI so a circle sitting on a square leaves the square's
  # corners showing: two markers, not one.
  for x, y, m in sorted(rows, key=lambda r: r[2].provider != "openai"):
    ax.scatter([x], [y], s=78, marker=MARKER[m.provider], color=t[m.provider],
               edgecolors=t["surface"], linewidths=2, zorder=3)
    top = tops[m.alias] is m
    dx, dy = chart.labels.get(key(m), chart.labels.get(m.alias, (8, 0)) if top else (8, 0))
    lead = (dx * dx + dy * dy) ** 0.5 > 16
    ax.annotate(
      label(m, top), (x, y), xytext=(dx, dy), textcoords="offset points",
      ha="left" if dx >= 0 else "right", va="center", fontsize=9.5,
      color=t["ink"] if key(m) in on_front else t["ink2"],
      fontweight="semibold" if key(m) in on_front else "normal", zorder=4,
      arrowprops={"arrowstyle": "-", "color": t["muted"], "linewidth": 0.8,
                  "shrinkA": 1, "shrinkB": 5} if lead else None,
    )

  handles = [
    Line2D([], [], marker=MARKER[p], linestyle="none", markersize=8, color=t[p],
           markeredgecolor=t["surface"], label=PROVIDER_NAME[p]) for p in ("google", "openai")
  ] + [Line2D([], [], color=t["ink2"], alpha=0.55, linewidth=1.5,
              label="Best for the price (Pareto frontier)" if chart.slug == "cost-quality"
              else "Fastest for the quality (Pareto frontier)")]
  if multi:
    handles.append(Line2D([], [], color=t["ink2"], alpha=0.7, linewidth=1,
                          label="One model at several settings"))
  leg = ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=9,
                  labelcolor=t["ink2"], handletextpad=0.5, borderaxespad=0.3)
  leg.set_zorder(5)
  ax.text(0.0, 1.03, "Better: up and to the left", transform=ax.transAxes, fontsize=9.5,
          color=t["ink2"], ha="left", va="bottom")
  fig.tight_layout()
  OUT.mkdir(parents=True, exist_ok=True)
  path = OUT / f"{chart.slug}-{theme}.svg"
  fig.savefig(path, format="svg", transparent=True, metadata={"Date": None})
  plt.close(fig)
  return path


def table(points: list[Model], arena: dict[str, tuple[float, str]]) -> str:
  lines = ["| Model | `--quality` | Cost | Time | Artificial Analysis | Arena |",
           "| --- | --- | ---: | ---: | ---: | ---: |"]
  for m in sorted(points, key=lambda m: -(m.elo or 0)):
    cost = f"${m.cost:.3f}" if m.cost is not None else "n/a"
    secs = f"{m.seconds:.0f} s" if m.seconds is not None else "n/a"
    score, rank = arena.get(m.alias, (None, ""))
    arena_cell = f"{score:.0f} (#{rank})" if score is not None else "n/a"
    lines.append(f"| `{m.alias}` | {m.setting} | {cost} | {secs} | "
                 f"{m.elo:.0f} (#{m.aa_rank}) | {arena_cell} |")
  return "\n".join(lines)


def main() -> None:
  points, arena = load()
  cost = Chart(
    slug="cost-quality", xlabel="Cost per image, 1024×1024, at the benchmarked setting (log scale)",
    xticks=[0.01, 0.02, 0.05, 0.1, 0.2], xfmt="${:g}", xlim=(0.008, 0.36), ylim=(890, 1225),
    labels={
      "oai:gi1-mini": (4, 13), "gdm:nb2-lite": (-9, 6), "gdm:nb2": (-9, 8),
      "oai:gi1.5": (18, 4), "gdm:nbp": (18, -13), "oai:gi1": (9, 0),
      "oai:gi2.5": (-18, 16), "oai:gi2.5-flare": (-18, -6), "oai:gi2": (-18, -18),
    },
  )
  speed = Chart(
    slug="speed-quality", xlabel="Median generation time in seconds (log scale)",
    xticks=[2, 5, 10, 20, 50, 100], xfmt="{:g} s", xlim=(2, 220), ylim=(1075, 1215),
    labels={
      "gdm:nb2-lite": (9, -6), "gdm:nb2": (9, 6), "gdm:nbp": (9, -6), "oai:gi1.5": (9, 6),
      "oai:gi2.5-flare": (-10, 6), "oai:gi2.5": (-10, 7), "oai:gi2": (-10, -8),
    },
  )
  cost_rows = [(m.cost, m.elo, m) for m in points if m.cost and m.elo]
  speed_rows = [(m.seconds, m.elo, m) for m in points if m.seconds and m.elo]
  for theme in THEMES:
    for chart, rows in ((cost, cost_rows), (speed, speed_rows)):
      print("wrote", draw(chart, rows, theme).relative_to(ROOT))
  counts: dict[str, int] = {}
  for m in points:
    if m.elo is not None:
      counts[m.alias] = counts.get(m.alias, 0) + 1
  multi = sorted(a for a, n in counts.items() if n > 1)
  print("scored at several settings:", ", ".join(multi) or "none")
  print("speed chart leaves out:", ", ".join(sorted({m.alias for m in points if not m.seconds})))
  print()
  print(table(points, arena))


if __name__ == "__main__":
  main()
