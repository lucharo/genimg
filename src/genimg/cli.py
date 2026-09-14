"""Typer CLI. `genimg PROMPT [opts]` is the default action; subcommands are utilities."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, NoReturn

import click
import typer
from rich.console import Console
from rich.markup import escape as _rich_escape
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from . import (
  __version__,
  config,
  cost,
  discovery,
  diversify,
  history,
  metadata,
  provenance,
  providers,
  registry,
)
from . import grid as grid_module
from . import setup as setup_module
from .auth import resolve as auth_resolve
from .generate import generate as run_generate
from .interfaces import GenerateRequest, IImageGen

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

    NOTE (deferred): this scrapes rendered help text for panel titles, so it is fragile
    to typer/rich_click rendering changes. Kept because it works and a clean reimplementation
    is non-trivial. If option panels ever stop showing in `genimg -h`, start here.
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

First-time setup: `genimg setup`. Subcommands: auth, models, setup, skills, config."""


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
_PANEL_GOOGLE = "Google-only (Gemini Image)"
_PANEL_OPENAI = "OpenAI-only (gpt-image-*)"


@_app.command("_run", hidden=True)
def _run(
  prompt: Annotated[str, typer.Argument(help="Text prompt.")],
  refs: Annotated[list[Path] | None, typer.Argument(help="Reference image paths (space-separated, after PROMPT).")] = None,
  model: Annotated[str | None, typer.Option("-m", "--model", rich_help_panel=_PANEL_CORE,
    help="Model alias (gdm:nb2, oai:gi2, ...) or canonical id. Defaults to the user-set default; if none, pass -m or run `genimg setup`.")] = None,
  profile: Annotated[str | None, typer.Option("--profile", rich_help_panel=_PANEL_CORE,
    help="Auth profile name from config.toml ([profiles.NAME]). Default: the provider's configured profile, else env auto-detection.")] = None,
  name: Annotated[str | None, typer.Option("--name", rich_help_panel=_PANEL_CORE,
    help="Optional human-readable generation name (duplicates allowed).")] = None,
  input: Annotated[Path | None, typer.Option("-i", "--input", rich_help_panel=_PANEL_CORE,
    help="Input image to edit (image-to-image).")] = None,
  diverse: Annotated[bool, typer.Option("-d", "--diverse", rich_help_panel=_PANEL_CORE,
    help="Diversify the -n generations — usually what you want with -n; plain -n converges on "
         "near-duplicates for simple subjects. Parallel mode: #1 keeps the base prompt, the rest each get "
         "a distinct style/composition delta from a curated list (recorded in metadata + grid). "
         "Batch mode (Gemini only): the model is asked to differentiate its n takes itself. Requires -n >= 2.")] = False,
  deltas_arg: Annotated[str | None, typer.Option("--deltas", rich_help_panel=_PANEL_CORE,
    help='Your own diversity deltas (implies -d): comma-separated ("isometric, blueprint, macro photo") '
         'or @file with one delta per line. Applied in order to generations #2..#n (#1 keeps the base prompt). '
         'Prefer this over the built-in pool when the subject is not an illustration/logo — '
         'pass deltas that fit diagrams, photos, etc. Parallel mode only.')] = None,
  n: Annotated[int, typer.Option("-n", "--num", min=1, max=10, rich_help_panel=_PANEL_CORE,
    help="Number of variants 1-10 (n>1 runs in parallel). Pair with -d for deliberate variety.")] = 1,
  mode: Annotated[str | None, typer.Option("--mode", rich_help_panel=_PANEL_CORE,
    help="parallel = n separate API requests (default); batch = ONE n-image "
         "request, Google only: Gemini multi-image response (pair with -d for a model-curated set; "
         "may return fewer than n). Rejected on OpenAI — gpt-image n>1 "
         "returns near-duplicate independent samples (verified live), i.e. wasted spend.")] = None,
  aspect_ratio: Annotated[str | None, typer.Option("-a", "--aspect-ratio", rich_help_panel=_PANEL_CORE,
    help="Output aspect ratio. Options depend on the selected model.")] = None,
  output: Annotated[Path | None, typer.Option("-o", "--output", rich_help_panel=_PANEL_OUTPUT,
    help="Output PNG path. Default: ~/.genimg/generations/<id>.png")] = None,
  grid: Annotated[bool, typer.Option("-g", "--grid", rich_help_panel=_PANEL_OUTPUT,
    help="When n>=2, also write HTML grid to ~/.genimg/grids/<id>.html.")] = False,
  open_after: Annotated[bool, typer.Option("--open", rich_help_panel=_PANEL_OUTPUT,
    help="Open the grid (n>1) or first image (n=1) in browser.")] = False,
  resolution: Annotated[str | None, typer.Option("-r", "--resolution", rich_help_panel=_PANEL_CORE,
    help="512 | 1K | 2K | 4K. Options depend on the selected model.")] = None,
  quality: Annotated[str | None, typer.Option("-q", "--quality", rich_help_panel=_PANEL_OPENAI,
    help="low | medium (default) | high | auto; GPT Image 2.5 also supports xhigh | max.")] = None,
  thinking_level: Annotated[str | None, typer.Option("--thinking", rich_help_panel=_PANEL_GOOGLE,
    help="minimal | high. Gemini 3.1 Flash Image only; high trades latency for more reasoning.")] = None,
  auth: Annotated[str | None, typer.Option("--auth", rich_help_panel=_PANEL_OPENAI,
    help="azure | native — force an OpenAI auth mode for this run (default: profile, else env auto-detect).")] = None,
  region: Annotated[str | None, typer.Option("--region", rich_help_panel=_PANEL_GOOGLE,
    help="Override registry region (e.g. global, us-central1).")] = None,
  project: Annotated[str | None, typer.Option("--project", rich_help_panel=_PANEL_GOOGLE,
    help="GCP project for Vertex (else config.gcp_project / GOOGLE_CLOUD_PROJECT / SA-JSON / gcloud).")] = None,
  dry_run: Annotated[bool, typer.Option("--dry-run", rich_help_panel=_PANEL_OUTPUT,
    help="Print model + estimated cost + params, don't call the API.")] = False,
):
  if name is not None:
    if "\n" in name or "\r" in name:
      _die("--name must be one line")
    name = name.strip() or None
  diverse = diverse or deltas_arg is not None
  if diverse and n < 2:
    _die("--diverse requires -n >= 2 (diversity across a single image is meaningless). Try -n 4 -d.")
  if mode is not None and mode not in ("parallel", "batch"):
    _die(f"--mode must be 'parallel' or 'batch', got {mode!r}")
  custom_pool = None
  if deltas_arg is not None:
    if mode == "batch":
      _die("--deltas is a parallel-mode mechanism (one delta per request); with --mode batch "
           "the model diversifies its own takes. Drop --deltas or use --mode parallel.")
    try:
      custom_pool = diversify.parse_deltas_arg(deltas_arg)
    except (ValueError, OSError) as e:
      _die(f"--deltas: {e}" if not str(e).startswith("--deltas") else str(e))

  user_cfg = config.load()
  model_was_explicit = model is not None
  resolved = model or user_cfg.get("default_model")
  if not resolved:
    _die(
      "no model specified. Pass -m <alias> (e.g. -m gdm:nb or -m oai:gi2), "
      "set a default with `genimg models set-default <alias>`, or run `genimg setup`. "
      "See `genimg models` for the full list."
    )
  try:
    alias, spec = registry.resolve(resolved)
  except ValueError as e:
    console.print(f"[red]unknown model:[/red] {e}\n")
    _list_models(refresh=False, show_aliases=True)
    raise typer.Exit(1)

  provider = providers.get(spec.provider)
  caps = provider.capabilities(spec.model_id)
  if auth == "direct":
    auth = "native"  # pre-profile spelling

  # Apply config defaults for generation params (flag → config → built-in).
  resolution_was_explicit = resolution is not None
  aspect_was_explicit = aspect_ratio is not None
  quality_was_explicit = quality is not None
  resolution, aspect_ratio = _compatible_size_defaults(
    caps, resolution, aspect_ratio,
    user_cfg.get("default_resolution"), user_cfg.get("default_aspect_ratio"),
  )
  if caps.qualities:
    quality = quality or user_cfg.get("default_quality")

  _validate_provider_flags(
    provider, caps, quality=quality, region=region, project=project, auth=auth,
    resolution=resolution, aspect_ratio=aspect_ratio, refs=refs, input=input,
    model_id=spec.model_id, mode=mode, diverse=diverse, thinking_level=thinking_level,
  )
  auth_info = auth_resolve.info(spec.provider, profile_name=profile, force_mode=auth, cfg=user_cfg)  # display only

  gen_id = metadata.make_id(prompt, spec.model_id)
  out_path = output if output is not None else metadata.auto_output_path(gen_id)
  planned_paths = _planned_output_paths(out_path, n)
  planned_grid = metadata.auto_grid_path(gen_id) if grid and n > 1 else None

  # Diverse mechanics differ by mode: parallel gets per-request curated deltas;
  # batch (Gemini) asks the model to differentiate its n takes in the one request.
  batch_diverse = diverse and mode == "batch"
  if diverse and not batch_diverse:
    try:
      deltas = diversify.pick_deltas(n, pool=custom_pool)
    except ValueError as e:
      _die(str(e))
  else:
    deltas = None
  variants = [diversify.apply(prompt, d) for d in deltas] if deltas else None

  effective_q = (quality or "medium") if caps.qualities else None
  params = [f"n={n}"]
  if mode:
    params.append(f"mode={mode}")
  if diverse:
    params.append("diverse")
  if effective_q:
    params.append(f"q={effective_q}{'' if quality_was_explicit else ' (default)'}")
  if resolution:
    params.append(f"r={resolution}{'' if resolution_was_explicit else ' (default)'}")
  if aspect_ratio:
    params.append(f"a={aspect_ratio}{'' if aspect_was_explicit else ' (default)'}")
  if thinking_level:
    params.append(f"thinking={thinking_level}")

  resolved_size = caps.resolved_size(resolution, aspect_ratio)
  est_cost = cost.estimate(provider=spec.provider, model_id=spec.model_id, n=n,
                           quality=effective_q, resolution=resolution)
  auth_mode_str = auth_info.mode + (f"@{auth_info.profile}" if auth_info.profile else "")
  cost_label = (f"{provider.label} (usage limits apply)" if provider.billing == "subscription"
                else f"{cost.format_usd(est_cost)} (estimate)")
  default_marker = "" if model_was_explicit else " [dim](default)[/dim]"

  console.print(
    f"[cyan]genimg[/cyan] [magenta]{spec.provider}/{auth_mode_str}[/magenta] "
    f"{alias}{default_marker} → [bold]{spec.model_id}[/bold]"
  )
  prompt_preview = prompt if len(prompt) <= 80 else prompt[:77] + "…"
  # Escape user input — bracketed prompts would otherwise be parsed as Rich markup.
  console.print(f'  [dim]prompt[/dim]   "{_rich_escape(prompt_preview)}"')
  if name:
    console.print(f"  [dim]name[/dim]     {_rich_escape(name)}")
  if input:
    console.print(
      f"  [dim]{'input':<7}[/dim]  {_rich_escape(_short_path(input))}", soft_wrap=True
    )
  for i, ref in enumerate(refs or []):
    row_label = "refs" if i == 0 else ""
    console.print(
      f"  [dim]{row_label:<7}[/dim]  #{i + 1} {_rich_escape(_short_path(ref))}",
      soft_wrap=True,
    )
  size_note = f" → {resolved_size}" if resolved_size else ""
  console.print(f"  [dim]params[/dim]   {' '.join(params)}{size_note}")
  console.print(f"  [dim]cost[/dim]     {cost_label}  [dim]id={gen_id}[/dim]")
  if provider.runtime_selects_model:
    console.print(f"  [dim]runtime[/dim]  {provider.label} selects the image model and size; aspect ratio is a prompt request.")
  _print_planned_paths(planned_paths)
  if deltas:
    for i, d in enumerate(deltas):
      row_label = "deltas" if i == 0 else ""
      console.print(f"  [dim]{row_label:<7}[/dim]  #{i + 1} {_rich_escape(d) if d else '(base prompt)'}")
  elif batch_diverse:
    console.print("  [dim]diverse[/dim]  model-coordinated: the single batched request asks for deliberately different takes")
  elif n >= 2 and mode != "batch":  # -d/--deltas guidance doesn't apply to batch submissions
    console.print(
      "  [dim]hint[/dim]     plain -n often converges on near-duplicates — add -d for curated variety, "
      'or pass your own subject-appropriate deltas: --deltas "isometric, blueprint, macro photo" (or --deltas @file, one per line)'
    )
  if planned_grid:
    console.print(f"  [dim]grid[/dim]     {_short_path(planned_grid)}")
  if effective_q == "high":
    console.print("[yellow]heads-up:[/yellow] -q high on gpt-image-2 is 30-90s/image. Try -q medium or -q low for speed.")

  if dry_run:
    console.print("[dim]dry-run: no API call made.[/dim]")
    return

  t0 = time.time()

  req = GenerateRequest(
    prompt=prompt, output=out_path, model=resolved,
    refs=refs or [], input=input, n=n,
    resolution=resolution, aspect_ratio=aspect_ratio, quality=quality,
    thinking_level=thinking_level,
    region=region, project=project, prompt_variants=variants,
    mode=mode, diverse=diverse,
  )
  try:
    with Progress(
      SpinnerColumn(),
      TextColumn("[progress.description]{task.description}"),
      TimeElapsedColumn(),
      console=console,
      transient=True,
    ) as progress:
      label = _progress_label(n, grid, mode)
      progress.add_task(label, total=None)
      result = run_generate(req, profile=profile, auth_mode=auth)
  except RuntimeError as e:
    console.print(f"[red]error:[/red] {e}")
    raise typer.Exit(2)
  except Exception as e:
    console.print(f"[red]error[/red] ({type(e).__name__}): {e}")
    raise typer.Exit(2)

  elapsed = time.time() - t0
  for p in result.paths:
    console.print(f"  [green]wrote[/green] {p} [dim]({p.stat().st_size:,}B)[/dim]", soft_wrap=True)
  for err in result.errors:
    console.print(f"  [yellow]skipped[/yellow] {_rich_escape(err)}", soft_wrap=True)

  # On partial success paths is compacted — realign per-generation deltas by the
  # surviving original indices, or image #3 would inherit failed #2's delta.
  output_deltas = deltas
  if deltas is not None and result.indices is not None:
    output_deltas = [deltas[i] for i in result.indices]

  meta = metadata.build(
    gen_id=gen_id, prompt=prompt, alias=alias, spec=spec, paths=result.paths,
    n=n, cost_usd=est_cost, input=input, refs=refs,
    resolution=resolution, aspect_ratio=aspect_ratio, quality=quality,
    thinking_level=thinking_level, prompt_deltas=output_deltas, mode=mode, diverse=diverse,
    name=name,
  )
  metadata.embed_into_images(meta)
  meta_path = metadata.save(meta, gen_id)

  written_grid: Path | None = None
  if grid and len(result.paths) > 1:
    target = planned_grid or metadata.auto_grid_path(gen_id)
    written_grid, total = grid_module.render(result.paths, target, provider=spec.provider, quality=quality, meta=meta)
    meta = metadata.build(
      gen_id=gen_id, prompt=prompt, alias=alias, spec=spec, paths=result.paths,
      n=n, cost_usd=est_cost, input=input, refs=refs,
      resolution=resolution, aspect_ratio=aspect_ratio, quality=quality,
      thinking_level=thinking_level, grid_path=written_grid,
      prompt_deltas=output_deltas, mode=mode, diverse=diverse,
      name=name,
    )
    meta_path = metadata.save(meta, gen_id)
    console.print(f"  [cyan]grid[/cyan] {written_grid} [dim](est. {cost.format_usd(total)})[/dim]", soft_wrap=True)
  elif grid and len(result.paths) == 1:
    console.print("[dim]--grid ignored: needs n>=2[/dim]")

  console.print(
    f"  [dim]cost {cost_label}  •  {elapsed:.1f}s  •  meta {meta_path}[/dim]",
    soft_wrap=True,
  )

  _print_provenance(meta)

  if open_after and (written_grid or result.paths):
    grid_module.open_in_browser(written_grid or result.paths[0])


def _print_provenance(meta: dict) -> None:
  console.print(f"  reported generator: {provenance.describe(meta.get('outputs', []))} (C2PA, unverified)", markup=False)
  console.print(f"  billing: {cost.billing_label(meta)}; theoretical API equivalent: "
                f"{cost.format_equivalent(meta.get('api_equivalent_cost'))} (rough output-only estimate)", markup=False)


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
  cached = None if refresh or json_out else discovery.load_cache()
  if not json_out:
    if refresh:
      n_models = len(registry.all_canonical())
      console.print(f"[dim]refreshing {n_models} model probe(s) in parallel...[/dim]")
    elif cached is None:
      n_models = len(registry.all_canonical())
      console.print(f"[dim]first probe of {n_models} model(s) in parallel — this may take a few minutes...[/dim]")
    elif discovery.is_cache_stale(cached):
      n_models = len(registry.all_canonical())
      console.print(
        f"[dim]cache age: {_fmt_age(discovery.cache_age_seconds(cached))}; "
        f"refreshing {n_models} model probe(s) in parallel...[/dim]"
      )
    else:
      console.print("[dim]" + " | ".join(f"{name}: {_auth_summary(i)}" for name, i in auth_resolve.all_info().items()) + "[/dim]")
      console.print("[dim]loading cache (--refresh to re-probe)...[/dim]")
  probes, age = discovery.get_or_probe(refresh=refresh, cached=cached)

  if json_out:
    import json as _json
    payload = []
    for alias, spec in registry.all_canonical().items():
      p = probes.get(alias)
      payload.append({
        "alias": alias, "model_id": spec.model_id, "provider": spec.provider,
        "region": spec.region, "status": p.status if p else "unknown",
        "is_default": alias == config.get_default_model(),
      })
    typer.echo(_json.dumps(payload, indent=2))
    return

  current_default = config.get_default_model()
  table = Table(title=f"genimg models  •  cache age: {_fmt_age(age)}  •  default: {current_default or '(none — pass -m)'}")
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
  if any((p.status if p else "") == "missing" for p in probes.values()):
    console.print(
      "[dim]missing = not enumerated by the provider's list endpoint; on Vertex this can be a "
      "false negative (Model Garden models may still generate). Confirm with a direct run.[/dim]"
    )


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
    try:
      canonical, spec = registry.resolve(user_default)
    except ValueError as e:
      _die(
        f"{_rich_escape(str(e))} Replace the saved default with "
        "`genimg models set-default gdm:nb2`, or remove it with "
        "`genimg models clear-default`."
      )
    console.print(f"[bold]{canonical}[/bold]  ({spec.provider} / {spec.model_id})  [dim]from {config.CONFIG_PATH}[/dim]")
  else:
    console.print("[dim]no default model set. Pass -m each run, or set one with `genimg models set-default <alias>`.[/dim]")


@models_app.command("clear-default", help="Remove the user-set default (after this, -m is required).")
def models_clear_default():
  config.clear_default_model()
  console.print("[green]cleared.[/green] No default set — pass -m each run, or `genimg models set-default <alias>`.")


# ────────────────────── setup command ──────────────────────

@_app.command("setup", help="Interactive wizard: detect creds, pick providers, save config.")
def setup_cmd():
  setup_module.run_setup()


# ────────────────────── auth command ──────────────────────

@_app.command("auth", help="Show auth status for every provider and profile.")
def auth_cmd(
  check: Annotated[bool, typer.Option("--check", help="Run a tiny live generation probe per provider (Codex: login only).")] = False,
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a Rich table (agent-friendly).")] = False,
  modes: Annotated[bool, typer.Option("--modes", help="List every auth mode and the env vars it auto-detects.")] = False,
):
  if modes:
    _print_auth_modes(json_out)
    return
  cached = discovery.load_fresh_cache()
  probes = {a: p["status"] for a, p in (cached or {}).get("probes", {}).items()}
  infos = auth_resolve.all_info()
  rows = [(p, infos[p.name], f"{p.alias_prefix}:") for p in providers.all_providers()]

  if json_out:
    import json as _json
    payload = {p.name: {**info.as_dict(),
                        "models_listed": sum(1 for a, s in probes.items() if a.startswith(prefix) and _status_counts_as_available(s)),
                        "models_total": sum(1 for a in probes if a.startswith(prefix))}
               for p, info, prefix in rows}
    typer.echo(_json.dumps(payload, indent=2))
    return

  table = Table(title="genimg auth")
  table.add_column("provider", style="cyan")
  table.add_column("mode", style="magenta")
  table.add_column("source", style="dim")
  table.add_column("endpoint")
  table.add_column("credential", style="dim")
  table.add_column("ready", justify="center")
  table.add_column("models", justify="right")

  for p, info, prefix in rows:
    cohort = [s for a, s in probes.items() if a.startswith(prefix)]
    ok_probes = sum(1 for s in cohort if _status_counts_as_available(s))
    summary = f"{ok_probes}/{len(cohort)} listed" if cohort else "[yellow]no cache[/yellow]"
    if p.runtime_selects_model:
      summary = "runtime-selected"
    cred_cell = f"[green]✓[/green] {info.credential}" if info.credential != "-" else "[red]✗ unset[/red]"
    endpoint_cell = (info.endpoint if info.endpoint != "-"
                     else "[red]✗ not set[/red]" if info.mode == "azure" else "-")
    ready_cell = "[green]✓[/green]" if info.ok else "[red]✗[/red]"
    table.add_row(p.name, info.mode, info.source, endpoint_cell, cred_cell, ready_cell, summary)

  console.print(table)
  for p, info, _ in rows:
    if not info.ok and info.hint:
      console.print(f"  [yellow]{p.name}[/yellow] · {_rich_escape(info.hint)}")

  if all(info.mode == "unset" for _, info, _ in rows):
    console.print("[yellow]no providers configured.[/yellow] Run [bold]genimg setup[/bold] to get started.")
  if not cached:
    console.print("[dim]run `genimg models` to populate the probe cache.[/dim]")
  else:
    console.print(f"[dim]cache age: {_fmt_age(discovery.cache_age_seconds(cached))}  •  `genimg models --refresh` to re-probe[/dim]")

  if check:
    console.print("\n[dim]live probe...[/dim]")
    for p, info, _ in rows:
      model_id, region = p.probe_default()
      try:
        r = p.make(auth_resolve.resolve(p.name) if info.ok else None).probe(model_id, region)
        status = _color_status(r.status)
      except RuntimeError as e:
        status = f"[red]{_rich_escape(str(e))}[/red]"
      note = " (login only)" if p.runtime_selects_model else ""
      console.print(f"  {p.name} → {model_id:<24} {status}{note}")


def _auth_summary(info) -> str:
  return f"{info.mode} ({info.credential})" if info.mode != "unset" else "unset"


def _print_auth_modes(json_out: bool) -> None:
  """Every provider's auth modes with the env vars each auto-detects."""
  entries = [
    {"provider": p.name, "mode": cls.mode, "label": cls.label, "env": list(cls.env_vars),
     "settings": [sp.key for sp in cls.settings_spec]}
    for p in providers.all_providers() for cls in p.auth_modes
  ]
  if json_out:
    import json as _json
    typer.echo(_json.dumps(entries, indent=2))
    return
  table = Table(title="auth modes  •  config.toml: [profiles.NAME] provider = ..., auth = ...")
  table.add_column("provider", style="cyan")
  table.add_column("auth", style="magenta")
  table.add_column("what it is")
  table.add_column("env vars auto-detected", style="dim")
  table.add_column("profile settings", style="dim")
  for e in entries:
    table.add_row(e["provider"], e["mode"], e["label"], ", ".join(e["env"]) or "-", ", ".join(e["settings"]) or "-")
  console.print(table)


# ────────────────────── history commands ─────────────────────

history_app = typer.Typer(
  help="Read-only history of automatically recorded generations; list or browse interactively.",
  context_settings={"help_option_names": ["-h", "--help"]},
  invoke_without_command=True,
  no_args_is_help=False,
)
_app.add_typer(history_app, name="history")


@history_app.callback(invoke_without_command=True)
def _history_root(
  ctx: typer.Context,
  limit: Annotated[int, typer.Option("-n", "--limit", min=1, max=200, help="Max rows.")] = 20,
  summary: Annotated[bool, typer.Option("--summary", help="Aggregate total spend across all generations.")] = False,
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a Rich table.")] = False,
):
  if ctx.invoked_subcommand is not None:
    return
  _show_history(limit=limit, summary=summary, json_out=json_out)


def _show_history(limit: int, summary: bool, json_out: bool = False) -> None:
  if summary:
    total, count = history.total_spent()
    if json_out:
      import json as _json
      typer.echo(_json.dumps({"total_usd": round(total, 4), "generations": count}))
      return
    console.print(f"[bold green]${total:.4f}[/bold green] across {count} generation(s)")
    console.print("[dim]API estimates only; subscription usage and unknown costs are excluded.[/dim]")
    if count:
      console.print(f"[dim]avg ${total/count:.4f}/gen  •  reads ~/.genimg/metadata/*.json[/dim]")
    return

  entries, skipped = history.load(limit=limit)
  if json_out:
    import json as _json
    typer.echo(_json.dumps(entries, indent=2))
    return

  if not entries:
    console.print("[dim]no generations yet. Run `genimg \"a prompt\"` to start.[/dim]")
    if skipped:
      console.print(f"[yellow]{skipped} unreadable metadata sidecars skipped.[/yellow]")
    return

  table = Table(title=f"recent {len(entries)} generation(s)")
  table.add_column("time", style="dim")
  table.add_column("name", style="bold", min_width=12, max_width=24, overflow="fold")
  table.add_column("model", style="cyan", overflow="fold")
  table.add_column("prompt", ratio=3, overflow="fold")
  table.add_column("made/req", justify="right")
  table.add_column("cost", justify="right")
  table.add_column("output", style="dim", ratio=2, overflow="fold")
  for e in entries:
    paths = e.get("outputs", [])
    first = paths[0] if paths else None
    out = first.get("path", "?") if isinstance(first, dict) else first or "?"
    out_short = out.replace(str(Path.home()), "~")
    prompt = e.get("prompt", "")
    prompt_short = prompt[:100] + ("…" if len(prompt) > 100 else "")
    alias = e.get("alias", "?")
    model_id = e.get("model_id", "?")
    model = alias if alias == model_id else f"{alias}\n→ {model_id}"
    requested = int(e.get("n", len(paths) or 1))
    delivered = len(paths)
    image_count = str(delivered) if delivered == requested else f"{delivered}/{requested}"
    table.add_row(
      e.get("time", "")[:19].replace("T", " "),
      _rich_escape(e.get("name") or "-"),
      model,
      _rich_escape(prompt_short),
      image_count,
      "subscription\nAPI equiv. " + cost.format_equivalent(e.get("api_equivalent_cost"))
      if cost.billing_label(e) == "subscription" else cost.format_usd(e.get("cost_usd_estimated")) + "\nAPI",
      _rich_escape(out_short),
    )
  console.print(table)
  if skipped:
    console.print(f"[yellow]{skipped} unreadable metadata sidecars skipped.[/yellow]")
  console.print("[dim]Interactive browser: genimg history view[/dim]")


@history_app.command("view", help="Interactively browse all generated images and their metadata.")
def history_view_cmd():
  from . import history_view

  history_view.run()


# ────────────────────── cost command ──────────────────────

# Thin delegator to `history --summary`. Kept as a real command (not removed) because the
# root group routes an unknown first word to the hidden generate command — so a bare
# `genimg cost` would otherwise be treated as a prompt and could trigger a paid generation
# when a default model is set.
@_app.command("cost", help="Total estimated spend (shorthand for `history --summary`).")
def cost_cmd(
  json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
):
  _show_history(limit=20, summary=True, json_out=json_out)


# ────────────────────── grid command (standalone) ──────────────────────

@_app.command("grid", help="Render an HTML grid from existing image files.")
def grid_cmd(
  paths: Annotated[list[Path], typer.Argument(help="Image paths to include in the grid.")],
  output: Annotated[Path | None, typer.Option("-o", "--output", help="Output HTML path. Default: ~/.genimg/grids/<timestamp>.html")] = None,
  open_after: Annotated[bool, typer.Option("--open", help="Open the grid in the browser.")] = False,
):
  if not paths:
    console.print("[red]error:[/red] need at least one image path.")
    raise typer.Exit(1)
  for p in paths:
    if not p.exists():
      console.print(f"[red]error:[/red] not found: {p}")
      raise typer.Exit(1)
  target = output or metadata.auto_grid_path(metadata.make_id("grid", "standalone"))
  # No cost_total — provenance of arbitrary input files is unknown, so any estimate
  # would be misleading. The footer is omitted rather than guessed.
  written, _total = grid_module.render(paths, target)
  console.print(f"[green]wrote[/green] {written} [dim]({len(paths)} images)[/dim]")
  if open_after:
    grid_module.open_in_browser(written)


# ────────────────────── draw command (studio web app) ──────────────────────

@_app.command("draw", help="Open the draw studio: sketch/annotate on a canvas, generate via genimg.")
def draw_cmd(
  paths: Annotated[list[Path] | None, typer.Argument(
    help="Image files and/or directories to load into the studio (optional).")] = None,
  port: Annotated[int, typer.Option("--port", help="Port to serve on (auto-bumps if busy).")] = 8788,
  model: Annotated[str | None, typer.Option("-m", "--model",
    help="Initial model alias (default: your set default → gdm:nb2).")] = None,
  no_open: Annotated[bool, typer.Option("--no-open", help="Don't auto-open the browser.")] = False,
):
  from . import draw as draw_module

  sources = draw_module.discover_images(paths or [])
  if paths and not sources:
    console.print("[yellow]no images found in the given path(s); starting with an empty canvas.[/yellow]")

  # The studio can prompt-generate a first image, but later canvas iterations send -i,
  # so the selected model must remain image-editable. Canonicalize aliases; fall back to
  # gdm:nb2 otherwise.
  studio_aliases = [m["alias"] for m in draw_module.STUDIO_MODELS]
  requested = model or config.get_default_model() or "gdm:nb2"
  try:
    canonical = registry.resolve(requested)[0]
  except ValueError:
    canonical = requested
  if canonical in studio_aliases:
    default_model = canonical
  else:
    if model:
      console.print(f"[yellow]{requested!r} isn't an editable studio model; starting with gdm:nb2.[/yellow]")
    default_model = "gdm:nb2"

  try:
    draw_module.serve(sources, port=port, model=default_model, open_browser=not no_open)
  except RuntimeError as e:
    _die(str(e))


# ────────────────────── config sub-typer ──────────────────────

config_app = typer.Typer(
  help="Inspect / edit the saved config (~/.config/genimg/config.toml).",
  context_settings={"help_option_names": ["-h", "--help"]},
  invoke_without_command=True,
  no_args_is_help=False,
)
_app.add_typer(config_app, name="config")


@config_app.callback(invoke_without_command=True)
def _config_root(ctx: typer.Context):
  if ctx.invoked_subcommand is None:
    config_show()


@config_app.command("show", help="Print the current saved config (TOML).")
def config_show():
  data = config.load()
  if not data:
    console.print(f"[dim]no config yet at {config.CONFIG_PATH}. Run `genimg setup` to create one.[/dim]")
    return
  console.print(config.dumps(data).rstrip(), markup=False, highlight=False)
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
  help="Install bundled skills into agent harnesses (claude/codex/cursor/opencode).",
  context_settings={"help_option_names": ["-h", "--help"]},
  invoke_without_command=True,
  no_args_is_help=False,
)
_app.add_typer(skills_app, name="skills")


@skills_app.callback(invoke_without_command=True)
def _skills_root(ctx: typer.Context):
  if ctx.invoked_subcommand is None:
    skills_list()

_AGENT_SKILL_ROOTS = {
  "claude":   Path.home() / ".claude" / "skills",
  "codex":    Path.home() / ".codex" / "skills",
  "cursor":   Path.home() / ".cursor" / "skills",
  "opencode": Path.home() / ".opencode" / "skills",
}


def _skill_sources() -> dict[str, Path]:
  pkg_dir = Path(__file__).parent
  for candidate in (pkg_dir / "_skills", pkg_dir.parent.parent / "skills"):
    if candidate.exists():
      sources = {
        child.name: child
        for child in sorted(candidate.iterdir())
        if child.is_dir() and (child / "SKILL.md").exists()
      }
      if sources:
        return sources

  # Legacy source layout used before multiple skills were bundled.
  for candidate in (pkg_dir / "_skill", pkg_dir.parent.parent / "skill"):
    if (candidate / "SKILL.md").exists():
      return {"genimg": candidate}

  raise FileNotFoundError("skill assets not found in package")


def _resolve_agents(agent: str) -> list[str]:
  if agent == "all":
    return list(_AGENT_SKILL_ROOTS)
  if agent not in _AGENT_SKILL_ROOTS:
    console.print(f"[red]unknown agent {agent!r}. Choose: {', '.join(_AGENT_SKILL_ROOTS)} or 'all'.[/red]")
    raise typer.Exit(1)
  return [agent]


def _resolve_skill_names(skill: str, sources: dict[str, Path]) -> list[str]:
  if skill == "all":
    return list(sources)
  if skill not in sources:
    console.print(f"[red]unknown skill {skill!r}. Choose: {', '.join(sources)} or 'all'.[/red]")
    raise typer.Exit(1)
  return [skill]


@skills_app.command("path", help="Print bundled skill source paths.")
def skills_path(
  skill: Annotated[str, typer.Argument(help="Skill name or 'all'.")] = "genimg",
):
  sources = _skill_sources()
  skill_names = _resolve_skill_names(skill, sources)
  for skill_name in skill_names:
    if len(skill_names) == 1:
      console.print(str(sources[skill_name]), soft_wrap=True)
    else:
      console.print(f"{skill_name}: {sources[skill_name]}", soft_wrap=True)


@skills_app.command("install", help="Symlink bundled skills into one or more agent skill dirs.")
def skills_install(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "claude",
  skill: Annotated[str, typer.Argument(help="Bundled skill name or 'all'.")] = "all",
  force: Annotated[bool, typer.Option("--force", help="Replace existing symlinks.")] = False,
):
  sources = _skill_sources()
  for name in _resolve_agents(agent):
    root = _AGENT_SKILL_ROOTS[name]
    for skill_name in _resolve_skill_names(skill, sources):
      src = sources[skill_name]
      target = root / skill_name
      target.parent.mkdir(parents=True, exist_ok=True)
      if target.exists() or target.is_symlink():
        if not force:
          console.print(f"[yellow]{name}/{skill_name}:[/yellow] {target} exists (use --force or `skills update {name} {skill_name}`)")
          continue
        target.unlink() if target.is_symlink() else _rm_tree(target)
      # NOTE (deferred): symlink into the (possibly uv-tool-managed) package dir. A `uv tool`
      # upgrade can recreate that dir and break the link — re-run `genimg skills update`. A
      # copy-based install would survive upgrades but needs its own staleness detection.
      target.symlink_to(src)
      console.print(f"[green]installed → {name}/{skill_name}:[/green] {target}")


@skills_app.command("update", help="Re-link bundled skills in one or more agent dirs.")
def skills_update(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "all",
  skill: Annotated[str, typer.Argument(help="Bundled skill name or 'all'.")] = "all",
):
  sources = _skill_sources()
  for name in _resolve_agents(agent):
    root = _AGENT_SKILL_ROOTS[name]
    for skill_name in _resolve_skill_names(skill, sources):
      src = sources[skill_name]
      target = root / skill_name
      if not (target.exists() or target.is_symlink()):
        continue  # silently skip uninstalled
      target.parent.mkdir(parents=True, exist_ok=True)
      if target.is_symlink() and target.resolve() == src.resolve():
        console.print(f"[dim]{name}/{skill_name}: already current[/dim]")
        continue
      target.unlink() if target.is_symlink() else _rm_tree(target)
      target.symlink_to(src)
      console.print(f"[green]updated → {name}/{skill_name}:[/green] {target}")


@skills_app.command("uninstall", help="Remove bundled skill symlinks from one or more agent dirs.")
def skills_uninstall(
  agent: Annotated[str, typer.Argument(help="claude | codex | cursor | opencode | all")] = "all",
  skill: Annotated[str, typer.Argument(help="Bundled skill name or 'all'.")] = "all",
):
  sources = _skill_sources()
  for name in _resolve_agents(agent):
    root = _AGENT_SKILL_ROOTS[name]
    for skill_name in _resolve_skill_names(skill, sources):
      target = root / skill_name
      if not (target.exists() or target.is_symlink()):
        console.print(f"[dim]{name}/{skill_name}: not installed[/dim]")
        continue
      target.unlink() if target.is_symlink() else _rm_tree(target)
      console.print(f"[green]removed ← {name}/{skill_name}:[/green] {target}")


@skills_app.command("list", help="Show install state across all known agents.")
def skills_list():
  sources = _skill_sources()
  table = Table(title="skill installs")
  table.add_column("agent", style="cyan")
  table.add_column("skill")
  table.add_column("target", style="dim")
  table.add_column("status")
  for agent_name, root in _AGENT_SKILL_ROOTS.items():
    for skill_name, src in sources.items():
      target = root / skill_name
      if target.is_symlink() and target.resolve() == src.resolve():
        status = "[green]installed[/green]"
      elif target.exists() or target.is_symlink():
        status = "[yellow]other (link mismatch)[/yellow]"
      else:
        status = "[dim]not installed[/dim]"
      table.add_row(agent_name, skill_name, str(target), status)
  console.print(table)
  for skill_name, src in sources.items():
    console.print(f"[dim]source {skill_name}: {src}[/dim]")
  console.print("[dim]install: `genimg skills install` (all) or `genimg skills install codex genimg`[/dim]")


# ────────────────────── helpers ──────────────────────

_RESOLUTION_VALUES = set(providers.base.ALL_RESOLUTIONS)
_ASPECT_VALUES = set(providers.base.ALL_ASPECTS)


def _size_params_supported(caps: providers.Capabilities, resolution: str | None,
                           aspect_ratio: str | None) -> bool:
  """Return whether a resolution/aspect pair is valid without printing or exiting."""
  if resolution is not None and resolution not in _RESOLUTION_VALUES:
    return False
  if aspect_ratio is not None and aspect_ratio not in _ASPECT_VALUES:
    return False
  return caps.supports_size(resolution, aspect_ratio)


def _compatible_size_defaults(
  caps: providers.Capabilities,
  resolution: str | None,
  aspect_ratio: str | None,
  configured_resolution: str | None,
  configured_aspect: str | None,
) -> tuple[str | None, str | None]:
  """Apply global size defaults only when the selected model supports the resulting pair.

  Explicit flags are never discarded; incompatible config-only values fall back to provider
  defaults so a default chosen for one model cannot make another model unusable.
  """
  resolution_defaults = [configured_resolution, None] if resolution is None else [None]
  aspect_defaults = [configured_aspect, None] if aspect_ratio is None else [None]
  candidates = [(r, a) for r in resolution_defaults for a in aspect_defaults]
  candidates.sort(key=lambda pair: (pair[0] is None) + (pair[1] is None))
  for default_resolution, default_aspect in candidates:
    candidate_resolution = resolution if resolution is not None else default_resolution
    candidate_aspect = aspect_ratio if aspect_ratio is not None else default_aspect
    if _size_params_supported(caps, candidate_resolution, candidate_aspect):
      return candidate_resolution, candidate_aspect
  return resolution, aspect_ratio


def _short_path(p: Path) -> str:
  s = str(p)
  home = str(Path.home())
  return s.replace(home, "~", 1) if s.startswith(home) else s


def _planned_output_paths(out_path: Path, n: int) -> list[Path]:
  return [IImageGen.numbered_path(out_path, i, n) for i in range(n)]


def _print_planned_paths(paths: list[Path]) -> None:
  label = "output" if len(paths) == 1 else "outputs"
  for i, path in enumerate(paths):
    row_label = label if i == 0 else ""
    console.print(f"  [dim]{row_label:<7}[/dim]  {_short_path(path)}")


def _progress_label(n: int, grid: bool, mode: str | None = None) -> str:
  if n == 1:
    return "generating 1 image..."
  how = "in one batched request" if mode == "batch" else "in parallel"
  if grid:
    return f"generating {n} images for grid {how}..."
  return f"generating {n} images {how}..."


def _validate_provider_flags(
  provider: providers.Provider, caps: providers.Capabilities, *, quality, region, project, auth,
  resolution, aspect_ratio, refs, input, model_id: str | None = None, mode: str | None = None,
  diverse: bool = False, thinking_level: str | None = None,
) -> None:
  """Reject incompatible provider/flag combinations early with clear errors, using the
  provider's declared capabilities rather than provider-name branches."""
  refs = refs or []
  name = provider.name

  # Provider-neutral: every input/reference path must exist.
  for p in ([input] if input else []) + refs:
    if not p.exists():
      _die(f"input not found: {p}")

  if mode == "batch" and not caps.batch:
    if name == "openai":
      _die(
        "--mode batch on OpenAI is wasted spend: gpt-image n>1 returns near-duplicate independent "
        "samples of one prompt (verified live). Use the default parallel mode — add -d or "
        '--deltas "..." for variety — or switch to a Gemini model (-m gdm:nb2) for batch.'
      )
    _die(f"{model_id} does not support --resolution or --mode batch; {provider.label} selects the image size."
         if provider.runtime_selects_model else
         f"{model_id} does not support --mode batch; use the default parallel mode.")

  if quality is not None:
    if "quality" not in provider.flags:
      _die(f"--quality is OpenAI-only; ignored on provider={name!r}. Drop the flag or use -m oai:gi2.")
    if quality not in caps.qualities:
      _die(f"--quality for {model_id} must be one of {list(caps.qualities)}, got {quality!r}")

  if thinking_level is not None:
    if thinking_level not in {"minimal", "high"}:
      _die(f"--thinking must be minimal or high, got {thinking_level!r}")
    if not caps.thinking_levels:
      _die("--thinking is supported only by Gemini 3.1 Flash Image (-m gdm:nb2).")

  if resolution is not None and resolution not in _RESOLUTION_VALUES:
    _die(f"--resolution must be one of {sorted(_RESOLUTION_VALUES)}, got {resolution!r}")
  if aspect_ratio is not None and aspect_ratio not in _ASPECT_VALUES:
    _die(f"--aspect-ratio must be one of {sorted(_ASPECT_VALUES)}, got {aspect_ratio!r}")

  if provider.runtime_selects_model and resolution is not None:
    _die(f"{model_id} does not support --resolution or --mode batch; {provider.label} selects the image size.")

  if caps.sizes:
    if not caps.supports_size(resolution, aspect_ratio):
      from .providers.openai import size_error
      _die(size_error(resolution, aspect_ratio))
  else:
    if resolution is not None and resolution not in caps.resolutions:
      shown = ", ".join(sorted(caps.resolutions, key=providers.base._res_order)) or "provider default only"
      _die(f"{model_id} supports image sizes: {shown}.")
    if aspect_ratio is not None and caps.aspect_ratios and aspect_ratio not in caps.aspect_ratios:
      _die(f"{model_id} does not support aspect ratio {aspect_ratio}.")

  if (region is not None or project is not None) and not {"region", "project"} <= provider.flags:
    _die(f"--region/--project are Google-only; ignored on provider={name!r}.")

  if auth is not None:
    if "auth" not in provider.flags:
      _die(f"--auth is OpenAI-only; ignored on provider={name!r}.")
    if auth not in provider.modes:
      _die(f"--auth must be one of {', '.join(provider.modes)}, got {auth!r}")

  inputs = ([input] if input else []) + refs
  if caps.max_inputs is not None and len(inputs) > caps.max_inputs:
    _die(f"{provider.label} accepts max {caps.max_inputs} input images, got {len(inputs)}")
  for p in inputs:
    if caps.input_exts is not None and p.suffix.lower() not in caps.input_exts:
      _die(f"{provider.label} inputs must be {sorted(caps.input_exts)}, got {p.suffix} ({p.name})")
    if caps.max_input_mb is not None:
      mb = p.stat().st_size / 1_048_576
      if mb > caps.max_input_mb:
        _die(f"input {p.name} is {mb:.1f}MB, exceeds {provider.label} cap {caps.max_input_mb}MB")


def _die(msg: str) -> NoReturn:
  console.print(f"[red]error:[/red] {msg}")
  raise typer.Exit(1)


def _fmt_age(seconds: float) -> str:
  if seconds < 60:
    return f"{seconds:.0f}s"
  if seconds < 3600:
    return f"{seconds / 60:.0f}m"
  if seconds < 86400:
    return f"{seconds / 3600:.1f}h"
  return f"{seconds / 86400:.1f}d"


def _color_status(s: str) -> str:
  return {
    "listed": "[green]listed[/green]",
    "ready": "[green]login ready[/green]",
    "missing": "[yellow]missing[/yellow]",
    "working": "[green]working[/green]",
    "404": "[yellow]404[/yellow]",
    "403": "[red]403[/red]",
    "auth": "[red]auth[/red]",
    "error": "[red]error[/red]",
  }.get(s, s)


def _status_counts_as_available(s: str) -> bool:
  return s in {"listed", "working"}


def _rm_tree(p: Path) -> None:
  import shutil
  shutil.rmtree(p)


def app() -> None:
  _app()


if __name__ == "__main__":
  app()
