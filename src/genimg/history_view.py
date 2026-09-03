"""Interactive terminal browser for generation history."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps
from rich.style import Style
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Static

from . import grid as grid_module
from . import history


@dataclass(frozen=True)
class HistoryImage:
  generation: dict
  generation_id: str
  output_index: int
  output_count: int
  path: Path

  @property
  def key(self) -> str:
    return f"{self.generation_id}:{self.output_index}"

  @property
  def name(self) -> str | None:
    return self.generation.get("name")

  @property
  def output_label(self) -> str:
    return f"{self.output_index + 1}/{self.output_count}"


def flatten_entries(entries: list[dict]) -> list[HistoryImage]:
  """Expand generation records into one navigable row per output image."""
  items: list[HistoryImage] = []
  for entry in entries:
    outputs = entry.get("outputs", [])
    for index, output in enumerate(outputs):
      raw_path = output.get("path") if isinstance(output, dict) else output
      if not raw_path:
        continue
      items.append(HistoryImage(
        generation=entry,
        generation_id=str(entry.get("id", "?")),
        output_index=index,
        output_count=len(outputs),
        path=Path(raw_path),
      ))
  return items


@lru_cache(maxsize=64)
def _render_preview_cached(path: str, mtime_ns: int, width: int, height: int) -> Text:
  del mtime_ns  # part of the cache key; reading it again is unnecessary
  with Image.open(path) as source:
    image = ImageOps.contain(source.convert("RGB"), (max(1, width), max(2, height * 2)))

  rendered = Text()
  pixels = image.load()
  for y in range(0, image.height, 2):
    lower_y = min(y + 1, image.height - 1)
    for x in range(image.width):
      upper = pixels[x, y]
      lower = pixels[x, lower_y]
      rendered.append(
        "▀",
        style=Style(
          color=f"rgb({upper[0]},{upper[1]},{upper[2]})",
          bgcolor=f"rgb({lower[0]},{lower[1]},{lower[2]})",
        ),
      )
    if y + 2 < image.height:
      rendered.append("\n")
  return rendered


def render_preview(path: Path, *, width: int, height: int) -> Text:
  """Render an image as portable terminal-colour half blocks."""
  stat = path.stat()
  return _render_preview_cached(str(path), stat.st_mtime_ns, width, height)


class HelpScreen(ModalScreen[None]):
  CSS = """
  HelpScreen { align: center middle; background: $background 70%; }
  #help { width: 64; height: auto; padding: 1 2; border: round $accent; background: $surface; }
  """
  BINDINGS = [Binding("escape,q,?", "dismiss", "Close")]

  def compose(self) -> ComposeResult:
    yield Static(
      "j/k or arrows  move\n"
      "PgUp/PgDn or Ctrl-B/Ctrl-F  page\n"
      "g/Home, G/End  first/last\n"
      "[/]  previous/next sibling output\n"
      "Enter/o  open selected image\n"
      "r  reload history\n"
      "Tab  switch pane on narrow terminals\n"
      "q/Esc/Ctrl-C  quit",
      id="help",
      markup=False,
    )


class HistoryViewApp(App[None]):
  TITLE = "genimg history"
  CSS = """
  #body { height: 1fr; layout: horizontal; }
  #history-list { width: 42%; min-width: 32; }
  #detail-pane { width: 58%; }
  #preview { height: 2fr; padding: 1; content-align: center middle; overflow: hidden; }
  #details { height: 1fr; min-height: 10; padding: 1 2; overflow-y: auto; border-top: solid $primary-darken-2; }
  #status { height: 1; padding: 0 1; color: $text-muted; }
  #body.narrow #history-list { width: 1fr; min-width: 0; }
  #body.narrow #detail-pane { display: none; }
  #body.narrow.show-detail #history-list { display: none; }
  #body.narrow.show-detail #detail-pane { display: block; width: 1fr; }
  """
  BINDINGS = [
    Binding("j", "cursor_down", "Down", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("pagedown,ctrl+f", "page_down", "Page down", show=False),
    Binding("pageup,ctrl+b", "page_up", "Page up", show=False),
    Binding("home,g", "first", "First", show=False),
    Binding("end,shift+g", "last", "Last", show=False),
    Binding("left_square_bracket", "previous_sibling", "Previous output", show=False),
    Binding("right_square_bracket", "next_sibling", "Next output", show=False),
    Binding("enter,o", "open_image", "Open"),
    Binding("r", "reload", "Reload"),
    Binding("question_mark", "help", "Help"),
    Binding("tab", "toggle_pane", "Switch pane", show=False),
    Binding("q,escape,ctrl+c", "quit", "Quit"),
  ]

  def __init__(
    self,
    *,
    entries: list[dict] | None = None,
    skipped: int = 0,
    loader: Callable[[], tuple[list[dict], int]] | None = None,
    opener: Callable[[Path], object] | None = None,
  ) -> None:
    super().__init__()
    self._fixed_entries = entries
    self._fixed_skipped = skipped
    self._loader = loader or (lambda: history.load(limit=None))
    self._opener = opener or grid_module.open_in_browser
    self.items: list[HistoryImage] = []
    self.selected_item: HistoryImage | None = None
    self.details_text = ""
    self.preview_text = ""
    self.status_text = ""
    self.is_narrow = False

  def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal(id="body"):
      yield DataTable(id="history-list", cursor_type="row", zebra_stripes=True)
      with Vertical(id="detail-pane"):
        yield Static("Select an image", id="preview")
        yield Static("", id="details", markup=False)
    yield Static("", id="status", markup=False)
    yield Footer()

  def on_mount(self) -> None:
    table = self.query_one("#history-list", DataTable)
    table.add_columns("time", "name", "model", "image", "file")
    self._set_narrow(self.size.width < 90)
    self._reload_items(initial=True)
    table.focus()

  def on_resize(self, event: events.Resize) -> None:
    self._set_narrow(event.size.width < 90)

  def _set_narrow(self, narrow: bool) -> None:
    self.is_narrow = narrow
    body = self.query_one("#body")
    body.set_class(narrow, "narrow")
    if not narrow:
      body.remove_class("show-detail")

  def _source(self) -> tuple[list[dict], int]:
    if self._fixed_entries is not None:
      return self._fixed_entries, self._fixed_skipped
    return self._loader()

  def _reload_items(self, *, initial: bool = False) -> None:
    entries, skipped = self._source()
    self.items = flatten_entries(entries)
    table = self.query_one("#history-list", DataTable)
    table.clear(columns=False)
    for item in self.items:
      entry = item.generation
      table.add_row(
        str(entry.get("time", ""))[:16].replace("T", " "),
        item.name or "-",
        entry.get("alias") or entry.get("model_id") or "?",
        item.output_label,
        item.path.name,
        key=item.key,
      )
    noun = "sidecar" if skipped == 1 else "sidecars"
    self.status_text = (
      f"{len(self.items)} images from {len(entries)} generations"
      + (f" · {skipped} unreadable {noun} skipped" if skipped else "")
    )
    self.query_one("#status", Static).update(self.status_text)
    if self.items:
      table.move_cursor(row=0)
      self._select(0)
    else:
      self.selected_item = None
      self.details_text = "No generation images found."
      self.preview_text = "No preview."
      self.query_one("#details", Static).update(self.details_text)
      self.query_one("#preview", Static).update(self.preview_text)
    if not initial:
      self.notify("History reloaded")

  def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    self._select(event.cursor_row)

  def _select(self, index: int) -> None:
    if not 0 <= index < len(self.items):
      return
    item = self.items[index]
    self.selected_item = item
    self.details_text = self._format_details(item)
    self.query_one("#details", Static).update(self.details_text)
    self._load_preview(item)

  def _format_details(self, item: HistoryImage) -> str:
    entry = item.generation
    alias = entry.get("alias") or "?"
    model_id = entry.get("model_id") or "?"
    refs = entry.get("refs") or []
    outputs = entry.get("outputs") or []
    lines = [
      item.name or "(unnamed)",
      f"time: {entry.get('time', '?')}",
      f"id: {item.generation_id}",
      f"image: {item.output_label} (requested {entry.get('n', len(outputs))})",
      f"model: {alias} -> {model_id}",
      f"provider: {entry.get('provider', '?')}",
      f"cost: ${entry.get('cost_usd_estimated', 0):.4f} (generation)",
      f"path: {item.path}",
    ]
    if entry.get("input"):
      lines.append(f"input: {entry['input']}")
    lines.extend(f"ref: {ref}" for ref in refs)
    if isinstance(entry.get("grid"), dict) and entry["grid"].get("path"):
      lines.append(f"grid: {entry['grid']['path']}")
    params = [
      f"n={entry.get('n', 1)}",
      f"mode={entry.get('mode', 'auto')}",
      f"resolution={entry.get('resolution') or '-'}",
      f"aspect={entry.get('aspect_ratio') or '-'}",
      f"quality={entry.get('quality') or '-'}",
      f"thinking={entry.get('thinking_level') or '-'}",
    ]
    lines.extend((f"params: {' · '.join(params)}", "", "prompt:", str(entry.get("prompt", ""))))
    return "\n".join(lines)

  @work(exclusive=True, thread=True, group="preview")
  def _load_preview(self, item: HistoryImage) -> None:
    try:
      width = max(12, int(self.size.width * (0.55 if not self.is_narrow else 0.9)))
      height = max(6, int(self.size.height * 0.45))
      rendered = render_preview(item.path, width=width, height=height)
      plain = rendered.plain
    except FileNotFoundError:
      rendered = Text(f"Image not found:\n{item.path}", style="bold red")
      plain = rendered.plain
    except Exception as error:
      rendered = Text(f"Preview unavailable ({type(error).__name__}):\n{item.path}", style="yellow")
      plain = rendered.plain
    self.call_from_thread(self._apply_preview, item.key, rendered, plain)

  def _apply_preview(self, item_key: str, rendered: Text, plain: str) -> None:
    if self.selected_item is None or self.selected_item.key != item_key:
      return
    self.preview_text = plain
    self.query_one("#preview", Static).update(rendered)

  def _table(self) -> DataTable:
    return self.query_one("#history-list", DataTable)

  def action_cursor_down(self) -> None:
    self._table().action_cursor_down()

  def action_cursor_up(self) -> None:
    self._table().action_cursor_up()

  def action_page_down(self) -> None:
    self._table().action_page_down()

  def action_page_up(self) -> None:
    self._table().action_page_up()

  def action_first(self) -> None:
    if self.items:
      self._table().move_cursor(row=0)

  def action_last(self) -> None:
    if self.items:
      self._table().move_cursor(row=len(self.items) - 1)

  def _move_to_sibling(self, step: int) -> None:
    if self.selected_item is None:
      return
    target_index = self.selected_item.output_index + step
    for row, item in enumerate(self.items):
      if item.generation_id == self.selected_item.generation_id and item.output_index == target_index:
        self._table().move_cursor(row=row)
        return

  def action_previous_sibling(self) -> None:
    self._move_to_sibling(-1)

  def action_next_sibling(self) -> None:
    self._move_to_sibling(1)

  def action_open_image(self) -> None:
    if self.selected_item is not None and self.selected_item.path.exists():
      self._opener(self.selected_item.path)

  def action_reload(self) -> None:
    if self._fixed_entries is not None:
      return
    self._reload_items()

  def action_help(self) -> None:
    self.push_screen(HelpScreen())

  def action_toggle_pane(self) -> None:
    if self.is_narrow:
      self.query_one("#body").toggle_class("show-detail")


def run() -> None:
  HistoryViewApp().run()
