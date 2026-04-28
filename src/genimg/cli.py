"""Typer CLI. `genimg PROMPT [opts]` is the default action; subcommands are utilities."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import click
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import __version__, config, cost, discovery, history, metadata, registry
from . import grid as grid_module
from . import setup as setup_module
from .auth import google as auth_google
from .auth import openai as auth_openai
from .generate import generate as run_generate
from .interfaces import GenerateRequest

console = Console()


class _DefaultGroup(typer.core.TyperGroup):
  """Group that routes unknown first positional to a hidden default command,
  AND merges the default command's option panels into the root help."""
  default_cmd_name = "_run"
  subcommand_metavar = '"PROMPT" [OPTIONS] | SUBCOMMAND'

  def resolve_command(self, ctx, args):
    try:
      return super().resolve_command(ctx, args)
    except click.UsageError:
      args = list(args)
      args.insert(0, self.default_cmd_name)
      return super().resolve_command(ctx, args)

  def get_help(self, ctx):
    """Render group help + default command's named option panels (so `genimg -h` shows everything).

    rich_click renders help via console.print side-effects (not via return value),
    so we capture _run's help to a buffer, filter to named panels, and append.
    """
    import contextlib
    import io
    import sys

    super().get_help(ctx)  # renders group help to stdout
    default_cmd = self.commands.get(self.default_cmd_name)
    if default_cmd is None:
      return ""

    # Capture _run's help (otherwise it'd render to stdout + show Usage/Arguments/Options noise).
    sub_ctx = click.Context(default_cmd, info_name="", parent=ctx)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
      default_cmd.get_help(sub_ctx)
    captured = buf.getvalue()

    keep_panels = ("─ Core", "─ Output", "─ OpenAI", "─ Google")
    lines = captured.splitlines()
    start = next((i for i, line in enumerate(lines) if any(p in line for p in keep_panels)), None)
    if start is not None:
      sys.stdout.write("\n".join(lines[start:]) + "\n")
    return ""


_ROOT_HELP = """Multi-provider image gen.

Usage: genimg "PROMPT" [REF_PATHS...] [OPTIONS]
       genimg <subcommand> [...]

First-time setup: `genimg setup`. Subcommands: auth, models, setup, skills."""


def _version_callback(value: bool):
  if value:
    typer.echo(f"genimg {__version__}")
    raise typer.Exit()


_app = typer.Typer(
  name="genimg",
  cls=_DefaultGroup,
  help=_ROOT_HELP,
  context_settings={"help_option_names": ["-h", "--help"]},
  add_completion=False,
  invoke_without_command=True,
  no_args_is_help=True,
)


@_app.callback()
def _root_callback(
  version: Annotated[bool | None, typer.Option("--version", callback=_version_callback, is_eager=True,
    help="Show version and exit.")] = None,
):
  pass


_PANEL_CORE = "Core"
_PANEL_OUTPUT = "Output"
_PANEL_GOOGLE = "Google-only (Vertex/Imagen)"
_PANEL_OPENAI = "OpenAI-only (gpt-image-*)"


@_app.command("_run", hidden=True)
def _run(
  prompt: Annotated[str, typer.Argument(help="Text prompt.")],
  refs: Annotated[list[Path] | None, typer.Argument(help="Reference image paths (space-separated, after PROMPT).")] = None,
  model: Annotated[str | None, typer.Option("-m", "--model", rich_help_panel=_PANEL_CORE,
    help="Model alias (gdm:nb2, oai:gi2, ...) or canonical id. Defaults to user-set default → built-in.")] = None,
  input: Annotated[Path | None, typer.Option("-i", "--input", rich_help_panel=_PANEL_CORE,
    help="Input image to edit (image-to-image).")] = None,
  n: Annotated[int, typer.Option("-n", "--num", min=1, max=10, rich_help_panel=_PANEL_CORE,
    help="Number of variants 1-10 (n>1 runs in parallel).")] = 1,
  aspect_ratio: Annotated[str | None, typer.Option("-a", "--aspect-ratio", rich_help_panel=_PANEL_CORE,
    help="1:1 | 3:4 | 4:3 | 9:16 | 16:9.")] = None,
  output: Annotated[Path | None, typer.Option("-o", "--output", rich_help_panel=_PANEL_OUTPUT,
    help="Output PNG path. Default: ~/.genimg/generations/<id>.png")] = None,
  grid: Annotated[bool, typer.Option("-g", "--grid", rich_help_panel=_PANEL_OUTPUT,
    help="When n>=2, also write HTML grid to ~/.genimg/grids/<id>.html.")] = False,
  open_after: Annotated[bool, typer.Option("--open", rich_help_panel=_PANEL_OUTPUT,
    help="Open the grid (n>1) or first image (n=1) in browser.")] = False,
  resolution: Annotated[str | None, typer.Option("-r", "--resolution", rich_help_panel=_PANEL_CORE,
    help="1K | 2K | 4K. Honored on OpenAI + Imagen only; ignored by Gemini Image.")] = None,
  quality: Annotated[str | None, typer.Option("-q", "--quality", rich_help_panel=_PANEL_OPENAI,
    help="low | medium (default) | high | auto. high = 30-90s/image.")] = None,
  auth: Annotated[str | None, typer.Option("--auth", rich_help_panel=_PANEL_OPENAI,
    help="azure | direct (default: auto-detect from OPENAI_BASE_URL).")] = None,
  region: Annotated[str | None, typer.Option("--region", rich_help_panel=_PANEL_GOOGLE,
    help="Override registry region (e.g. global, us-central1).")] = None,
  project: Annotated[str | None, typer.Option("--project", rich_help_panel=_PANEL_GOOGLE,
    help="Override GCP project (default: gsk-rd-oaiml-kgapoc1-dev).")] = None,
  dry_run: Annotated[bool, typer.Option("--dry-run", rich_help_panel=_PANEL_OUTPUT,
    help="Print model + estimated cost + params, don't call the API.")] = False,
):
  resolved = model or config.get_default_model() or registry.DEFAULT
  try:
    alias, spec = registry.resolve(resolved)
  except ValueError as e:
    console.print(f"[red]unknown model:[/red] {e}\n")
    _list_models(refresh=False, show_aliases=True)
    raise typer.Exit(1)

  _validate_provider_flags(
    spec.provider, quality=quality, region=region, project=project, auth=auth,
    resolution=resolution, aspect_ratio=aspect_ratio, refs=refs, input=input,
    model_id=spec.model_id,
  )

  gen_id = metadata.make_id(prompt, spec.model_id)
  out_path = output if output is not None else metadata.auto_output_path(gen_id)

  effective_q = (quality or "medium") if spec.provider == "openai" else None
  params = [f"n={n}"]
  if effective_q:
    params.append(f"q={effective_q}{'' if quality else ' (default)'}")
  if resolution:
    params.append(f"r={resolution}")
  if aspect_ratio:
    params.append(f"a={aspect_ratio}")
  console.print(
    f"[cyan]genimg[/cyan] [{spec.provider}] {alias} → [bold]{spec.model_id}[/bold] "
    f"[dim]id={gen_id} {' '.join(params)}[/dim]"
  )
  if effective_q == "high":
    console.print("[yellow]heads-up:[/yellow] -q high on gpt-image-2 is 30-90s/image. Try -q medium or -q low for speed.")

  if dry_run:
    est = cost.estimate(provider=spec.provider, model_id=spec.model_id, n=n,
                        quality=effective_q, resolution=resolution)
    console.print(f"[dim]dry-run: would call {spec.model_id} ({n} image{'s' if n>1 else ''}). "
                  f"Estimated cost: ~${est:.4f}. No API call made.[/dim]")
    return

  t0 = time.time()

  req = GenerateRequest(
    prompt=prompt, output=out_path, model=resolved,
    refs=refs or [], input=input, n=n,
    resolution=resolution, aspect_ratio=aspect_ratio, quality=quality,
    region=region, project=project,
  )
  try:
    with Progress(
      SpinnerColumn(),
      TextColumn("[progress.description]{task.description}"),
      TimeElapsedColumn(),
      console=console,
      transient=True,
    ) as progress:
      label = f"generating {n} images in parallel..." if n > 1 else "generating 1 image..."
      progress.add_task(label, total=None)
      result = run_generate(req, force_openai_auth=auth)
  except RuntimeError as e:
    console.print(f"[red]error:[/red] {e}")
    raise typer.Exit(2)
  except Exception as e:
    console.print(f"[red]error[/red] ({type(e).__name__}): {e}")
    raise typer.Exit(2)

  est_cost = cost.estimate(provider=spec.provider, model_id=spec.model_id, n=n,
                           quality=effective_q, resolution=resolution)
  meta = metadata.build(
    gen_id=gen_id, prompt=prompt, alias=alias, spec=spec, paths=result.paths,
    n=n, cost_usd=est_cost, input=input, refs=refs,
    resolution=resolution, aspect_ratio=aspect_ratio, quality=quality,
  )
  meta_path = metadata.save(meta, gen_id)

  elapsed = time.time() - t0
  for p in result.paths:
    console.print(f"  [green]wrote[/green] {p} [dim]({p.stat().st_size:,}B)[/dim]", soft_wrap=True)
  console.print(
    f"  [dim]cost ~${est_cost:.4f}  •  {elapsed:.1f}s  •  meta {meta_path}[/dim]",
    soft_wrap=True,
  )

  written_grid: Path | None = None
  if grid and len(result.paths) > 1:
    target = metadata.auto_grid_path(gen_id)
    written_grid, total = grid_module.render(result.paths, target, provider=spec.provider, quality=quality)
    console.print(f"  [cyan]grid[/cyan] {written_grid} [dim](est. ${total:.2f})[/dim]", soft_wrap=True)
  elif grid and len(result.paths) == 1:
    console.print("[dim]--grid ignored: needs n>=2[/dim]")

  if open_after:
    grid_module.open_in_browser(written_grid or result.paths[0])


# ────────────────────── models sub-typer ──────────────────────

models_app = typer.Typer(
  help="Model registry: list, set/get/clear default. Aliases AND canonical model IDs accepted with -m.",
  context_settings={"help_option_names": ["-h", "--help"]},
  invoke_without_command=True,
  no_args_is_help=False,
)
_app.add_typer(models_app, name="models")


@models_app.callback(invoke_without_command=True)
def _models_root(
  ctx: typer.Context,
  refresh: Annotated[bool, typer.Option("--refresh", help="Force re-probe.")] = False,
  show_aliases: Annotated[bool, typer.Option("--aliases", help="Include alias-only entries.")] = False,
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a Rich table.")] = False,
):
  if ctx.invoked_subcommand is not None:
    return
  _list_models(refresh=refresh, show_aliases=show_aliases, json_out=json_out)


def _list_models(refresh: bool, show_aliases: bool, json_out: bool = False) -> None:
  cache_exists = discovery.load_cache() is not None
  if not cache_exists or refresh:
    n_models = len(registry.all_canonical())
    console.print(f"[dim]first probe of {n_models} model(s) — this may take ~30s...[/dim]")
  else:
    console.print(f"[dim]google: {auth_google.auth_mode()} | openai: {auth_openai.auth_mode()}[/dim]")
    console.print("[dim]loading cache (--refresh to re-probe)...[/dim]")
  t0 = time.time()
  probes, age = discovery.get_or_probe(refresh=refresh)
  elapsed = time.time() - t0

  if json_out:
    import json as _json
    payload = []
    for alias, spec in registry.all_canonical().items():
      p = probes.get(alias)
      payload.append({
        "alias": alias, "model_id": spec.model_id, "provider": spec.provider,
        "region": spec.region, "status": p.status if p else "unknown",
        "is_default": alias == (config.get_default_model() or registry.DEFAULT),
      })
    typer.echo(_json.dumps(payload, indent=2))
    return

  current_default = config.get_default_model() or registry.DEFAULT
  table = Table(title=f"genimg models  •  cache age: {_fmt_age(age)}  •  default: {current_default}")
  table.add_column("", width=1)
  table.add_column("alias", style="cyan")
  table.add_column("model_id")
  table.add_column("provider", style="magenta")
  table.add_column("region", style="dim")
  table.add_column("status")
  if show_aliases:
    table.add_column("aliases", style="dim")

  for alias, spec in sorted(registry.all_canonical().items(),
                            key=lambda kv: (kv[1].provider, -kv[1].quality_rank, kv[0])):
    p = probes.get(alias)
    marker = "[bold green]★[/bold green]" if alias == current_default else " "
    row = [marker, alias, spec.model_id, spec.provider, spec.region or "-",
           _color_status(p.status if p else "?")]
    if show_aliases:
      row.append(", ".join(registry.aliases_for(alias)))
    table.add_row(*row)

  console.print(table)
  console.print("[dim]★ = current default. Change with `genimg models set-default <alias>`.[/dim]")


@models_app.command("set-default", help="Pick a default model alias for `genimg PROMPT` (no -m).")
def models_set_default(alias: Annotated[str, typer.Argument(help="Alias or canonical id (e.g. gdm:nbp or gpt-image-2).")]):
  try:
    canonical, spec = registry.resolve(alias)
  except ValueError as e:
    console.print(f"[red]{e}[/red]")
    raise typer.Exit(1)
  config.set_default_model(canonical)
  if alias != canonical:
    console.print(f"[dim]resolved {alias!r} → {canonical}[/dim]")
  console.print(f"[green]default →[/green] {canonical} ({spec.provider} / {spec.model_id})")
  console.print(f"[dim]saved to {config.CONFIG_PATH}[/dim]")


@models_app.command("get-default", help="Show the current default model.")
def models_get_default():
  user_default = config.get_default_model()
  if user_default:
    canonical, spec = registry.resolve(user_default)
    console.print(f"[bold]{canonical}[/bold]  ({spec.provider} / {spec.model_id})  [dim]from {config.CONFIG_PATH}[/dim]")
  else:
    canonical, spec = registry.resolve(registry.DEFAULT)
    console.print(f"[bold]{canonical}[/bold]  ({spec.provider} / {spec.model_id})  [dim](built-in default; use `set-default` to override)[/dim]")


@models_app.command("clear-default", help="Remove the user-set default (revert to built-in).")
def models_clear_default():
  config.clear_default_model()
  console.print(f"[green]cleared.[/green] Built-in default: [bold]{registry.DEFAULT}[/bold]")


# ────────────────────── setup command ──────────────────────

@_app.command("setup", help="Interactive wizard: detect creds, pick providers, save config.")
def setup_cmd():
  setup_module.run_setup()


# ────────────────────── auth command ──────────────────────

@_app.command("auth", help="Show auth status for both providers.")
def auth_cmd(
  check: Annotated[bool, typer.Option("--check", help="Run a tiny live probe per provider.")] = False,
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a Rich table (agent-friendly).")] = False,
):
  cached = discovery.load_cache()
  probes = {a: p["status"] for a, p in (cached or {}).get("probes", {}).items()}

  rows = [("google", auth_google.auth_info(), "gdm:"), ("openai", auth_openai.auth_info(), "oai:")]

  if json_out:
    import json as _json
    payload = {name: {**info, "models_working": sum(1 for a, s in probes.items() if a.startswith(prefix) and s == "working"),
                      "models_total":  sum(1 for a in probes if a.startswith(prefix))} for name, info, prefix in rows}
    typer.echo(_json.dumps(payload, indent=2))
    return

  table = Table(title="genimg auth")
  table.add_column("provider", style="cyan")
  table.add_column("mode", style="magenta")
  table.add_column("source", style="dim")
  table.add_column("endpoint")
  table.add_column("credential", style="dim")
  table.add_column("models", justify="right")

  for name, info, prefix in rows:
    cohort = [s for a, s in probes.items() if a.startswith(prefix)]
    ok = sum(1 for s in cohort if s == "working")
    summary = f"{ok}/{len(cohort)} working" if cohort else "[yellow]no cache[/yellow]"
    table.add_row(name, info["mode"], info.get("source", "-"), info["endpoint"], info["credential"], summary)

  console.print(table)
  unset_count = sum(1 for _, info, _ in rows if info["mode"] == "unset")
  if unset_count == len(rows):
    console.print("[yellow]no providers configured.[/yellow] Run [bold]genimg setup[/bold] to get started.")
  if not cached:
    console.print("[dim]run `genimg models` to populate the probe cache.[/dim]")
  else:
    console.print(f"[dim]cache age: {_fmt_age(time.time() - cached['timestamp'])}  •  `genimg models --refresh` to re-probe[/dim]")

  if check:
    console.print("\n[dim]live probe...[/dim]")
    from .providers import GeminiImageGen, OpenAIImageGen
    g = GeminiImageGen().probe("gemini-2.5-flash-image", region="us-central1")
    o = OpenAIImageGen().probe("gpt-image-2")
    console.print(f"  google → gemini-2.5-flash-image  {_color_status(g.status)}")
    console.print(f"  openai → gpt-image-2             {_color_status(o.status)}")


# ────────────────────── history command ──────────────────────

@_app.command("history", help="List recent generations (reads ~/.genimg/metadata/).")
def history_cmd(
  limit: Annotated[int, typer.Option("-n", "--limit", min=1, max=200, help="Max rows.")] = 20,
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a Rich table.")] = False,
):
  entries = history.recent(limit=limit)
  if json_out:
    import json as _json
    typer.echo(_json.dumps(entries, indent=2))
    return

  if not entries:
    console.print("[dim]no generations yet. Run `genimg \"a prompt\"` to start.[/dim]")
    return

  table = Table(title=f"recent {len(entries)} generation(s)")
  table.add_column("time", style="dim")
  table.add_column("alias", style="cyan")
  table.add_column("prompt")
  table.add_column("n", justify="right")
  table.add_column("cost", justify="right")
  table.add_column("output", style="dim")
  for e in entries:
    paths = e.get("outputs", [])
    out = paths[0]["path"] if paths else "?"
    out_short = out.replace(str(Path.home()), "~")
    prompt_short = e.get("prompt", "")[:50] + ("…" if len(e.get("prompt", "")) > 50 else "")
    table.add_row(
      e.get("time", "")[:19].replace("T", " "),
      e.get("alias", "?"),
      prompt_short,
      str(e.get("n", 1)),
      f"${e.get('cost_usd_estimated', 0):.4f}",
      out_short,
    )
  console.print(table)


# ────────────────────── cost command ──────────────────────

@_app.command("cost", help="Show total estimated spend across all generations.")
def cost_cmd(
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
):
  total, count = history.total_spent()
  if json_out:
    import json as _json
    typer.echo(_json.dumps({"total_usd": round(total, 4), "generations": count}))
    return
  console.print(f"[bold green]${total:.4f}[/bold green] across {count} generation(s)")
  if count:
    console.print(f"[dim]avg ${total/count:.4f}/gen  •  reads ~/.genimg/metadata/*.json[/dim]")


# ────────────────────── config sub-typer ──────────────────────

config_app = typer.Typer(
  help="Inspect / edit the saved config (~/.config/genimg/config.json).",
  context_settings={"help_option_names": ["-h", "--help"]},
)
_app.add_typer(config_app, name="config")


@config_app.command("show", help="Print current saved config as JSON.")
def config_show():
  data = config.load()
  if not data:
    console.print(f"[dim]no config yet at {config.CONFIG_PATH}. Run `genimg setup` to create one.[/dim]")
    return
  import json as _json
  console.print(_json.dumps(data, indent=2))
  console.print(f"[dim]{config.CONFIG_PATH}[/dim]")


@config_app.command("path", help="Print the config file path.")
def config_path():
  typer.echo(str(config.CONFIG_PATH))


@config_app.command("edit", help="Open the config file in $EDITOR.")
def config_edit():
  config.open_in_editor()
  console.print(f"[dim]edited {config.CONFIG_PATH}[/dim]")


# ────────────────────── skills sub-typer ──────────────────────

skills_app = typer.Typer(
  help="Install the bundled skill into agent harnesses (claude/codex/cursor/opencode).",
  context_settings={"help_option_names": ["-h", "--help"]},
)
_app.add_typer(skills_app, name="skills")

_AGENT_TARGETS = {
  "claude":   Path.home() / ".claude" / "skills" / "genimg",
  "codex":    Path.home() / ".codex" / "skills" / "genimg",
  "cursor":   Path.home() / ".cursor" / "skills" / "genimg",
  "opencode": Path.home() / ".opencode" / "skills" / "genimg",
}


def _skill_source() -> Path:
  pkg_dir = Path(__file__).parent
  for candidate in (pkg_dir / "_skill", pkg_dir.parent.parent / "skill"):
    if candidate.exists():
      return candidate
  raise FileNotFoundError("skill assets not found in package")


def _resolve_agents(agent: str) -> list[str]:
  if agent == "all":
    return list(_AGENT_TARGETS)
  if agent not in _AGENT_TARGETS:
    console.print(f"[red]unknown agent {agent!r}. Choose: {', '.join(_AGENT_TARGETS)} or 'all'.[/red]")
    raise typer.Exit(1)
  return [agent]


@skills_app.command("path", help="Print the source path of the bundled skill (useful for `npx skills add`).")
def skills_path():
  console.print(str(_skill_source()))


@skills_app.command("install", help="Symlink the skill into one or more agent skill dirs.")
def skills_install(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "claude",
  force: Annotated[bool, typer.Option("--force", help="Replace existing symlinks.")] = False,
):
  src = _skill_source()
  for name in _resolve_agents(agent):
    target = _AGENT_TARGETS[name]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
      if not force:
        console.print(f"[yellow]{name}:[/yellow] {target} exists (use --force or `skills update {name}`)")
        continue
      target.unlink() if target.is_symlink() else _rm_tree(target)
    target.symlink_to(src)
    console.print(f"[green]installed → {name}:[/green] {target}")


@skills_app.command("update", help="Re-link the skill in one or more agent dirs.")
def skills_update(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "all",
):
  src = _skill_source()
  for name in _resolve_agents(agent):
    target = _AGENT_TARGETS[name]
    if not (target.exists() or target.is_symlink()):
      continue  # silently skip uninstalled
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == src.resolve():
      console.print(f"[dim]{name}: already current[/dim]")
      continue
    target.unlink() if target.is_symlink() else _rm_tree(target)
    target.symlink_to(src)
    console.print(f"[green]updated → {name}:[/green] {target}")


@skills_app.command("uninstall", help="Remove the skill symlink from one or more agent dirs.")
def skills_uninstall(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "all",
):
  for name in _resolve_agents(agent):
    target = _AGENT_TARGETS[name]
    if not (target.exists() or target.is_symlink()):
      console.print(f"[dim]{name}: not installed[/dim]")
      continue
    target.unlink() if target.is_symlink() else _rm_tree(target)
    console.print(f"[green]removed ← {name}:[/green] {target}")


@skills_app.command("list", help="Show install state across all known agents.")
def skills_list():
  src = _skill_source()
  table = Table(title="skill installs")
  table.add_column("agent", style="cyan")
  table.add_column("target", style="dim")
  table.add_column("status")
  for name, target in _AGENT_TARGETS.items():
    if target.is_symlink() and target.resolve() == src.resolve():
      status = "[green]installed[/green]"
    elif target.exists() or target.is_symlink():
      status = "[yellow]other (link mismatch)[/yellow]"
    else:
      status = "[dim]not installed[/dim]"
    table.add_row(name, str(target), status)
  console.print(table)
  console.print(f"[dim]source: {src}[/dim]")
  console.print("[dim]install elsewhere: `genimg skills install <agent>` or `npx skills add $(genimg skills path) --agent <agent>`[/dim]")


# ────────────────────── helpers ──────────────────────

_QUALITY_VALUES = {"low", "medium", "high", "auto"}
_RESOLUTION_VALUES = {"1K", "2K", "4K"}
_ASPECT_VALUES = {"1:1", "3:4", "4:3", "9:16", "16:9"}
_OPENAI_INPUT_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_OPENAI_MAX_INPUT_MB = 50
_OPENAI_MAX_INPUTS = 16


def _validate_provider_flags(
  provider: str, *, quality, region, project, auth, resolution, aspect_ratio, refs, input,
  model_id: str | None = None,
) -> None:
  """Reject incompatible provider/flag combinations early with clear errors."""
  refs = refs or []

  if quality is not None:
    if quality not in _QUALITY_VALUES:
      _die(f"--quality must be one of {sorted(_QUALITY_VALUES)}, got {quality!r}")
    if provider != "openai":
      _die(f"--quality is OpenAI-only; ignored on provider={provider!r}. Drop the flag or use -m oai:gi2.")

  if resolution and provider == "google" and model_id and not model_id.startswith("imagen-"):
    _die(
      f"--resolution is silently ignored by Gemini Image models (verified). "
      f"Drop the flag, switch to -m oai:gi2, or use Imagen (-m gdm:imagen4)."
    )

  if model_id and model_id.startswith("imagen-") and (input or refs):
    _die(
      "Imagen does not support --input or reference images (text-to-image only). "
      "Drop the flag(s), or switch to a Gemini Image model (-m gdm:nb2 / gdm:nbp) or OpenAI (-m oai:gi2)."
    )

  if provider == "openai":
    # Use the effective resolution (1K is the implicit default in _size_for) so bare
    # --aspect-ratio without --resolution gets the same upstream error as the explicit form.
    effective_res = resolution or "1K"
    if effective_res == "4K" and aspect_ratio in ("4:3", "3:4"):
      _die(
        "OpenAI: 4K + 4:3/3:4 exceeds total pixel cap (8.3M). "
        "Use 2K + 4:3/3:4 or 4K + 16:9/9:16."
      )
    if effective_res == "1K" and aspect_ratio in ("16:9", "9:16"):
      _die(
        "OpenAI: 16:9/9:16 at 1K falls below the 655k pixel min. "
        "Pass -r 2K (→ 2048x1152 / 1152x2048), or drop --aspect-ratio for the 1K square default."
      )

  if resolution is not None and resolution not in _RESOLUTION_VALUES:
    _die(f"--resolution must be one of {sorted(_RESOLUTION_VALUES)}, got {resolution!r}")
  if aspect_ratio is not None and aspect_ratio not in _ASPECT_VALUES:
    _die(f"--aspect-ratio must be one of {sorted(_ASPECT_VALUES)}, got {aspect_ratio!r}")

  if provider != "google" and (region is not None or project is not None):
    _die(f"--region/--project are Google-only; ignored on provider={provider!r}.")

  if provider != "openai" and auth is not None:
    _die(f"--auth is OpenAI-only; ignored on provider={provider!r}.")

  if provider == "openai":
    inputs = ([input] if input else []) + refs
    if len(inputs) > _OPENAI_MAX_INPUTS:
      _die(f"OpenAI accepts max {_OPENAI_MAX_INPUTS} input images, got {len(inputs)}")
    for p in inputs:
      if not p.exists():
        _die(f"input not found: {p}")
      if p.suffix.lower() not in _OPENAI_INPUT_EXTS:
        _die(f"OpenAI inputs must be {sorted(_OPENAI_INPUT_EXTS)}, got {p.suffix} ({p.name})")
      mb = p.stat().st_size / 1_048_576
      if mb > _OPENAI_MAX_INPUT_MB:
        _die(f"input {p.name} is {mb:.1f}MB, exceeds OpenAI cap {_OPENAI_MAX_INPUT_MB}MB")


def _die(msg: str) -> None:
  console.print(f"[red]error:[/red] {msg}")
  raise typer.Exit(1)


def _fmt_age(seconds: float) -> str:
  if seconds < 60:
    return f"{seconds:.0f}s"
  if seconds < 3600:
    return f"{seconds / 60:.0f}m"
  return f"{seconds / 3600:.1f}h"


def _color_status(s: str) -> str:
  return {
    "working": "[green]working[/green]",
    "404": "[yellow]404[/yellow]",
    "403": "[red]403[/red]",
    "auth": "[red]auth[/red]",
    "error": "[red]error[/red]",
  }.get(s, s)


def _rm_tree(p: Path) -> None:
  import shutil
  shutil.rmtree(p)


def app() -> None:
  _app()


if __name__ == "__main__":
  app()
