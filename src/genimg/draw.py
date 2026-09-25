"""genimg draw — a local "draw studio" web app.

`genimg draw [PATHS...]` starts a stdlib HTTP server that serves a single-page,
Excalidraw-style canvas: prompt-generate a first image or drop/annotate images
with vector strokes, then hit Generate. Canvas jobs flatten to a PNG; every job
spawns its OWN `genimg` subprocess in the background (concurrent), and the page
polls /status until done.
Results land in ~/.genimg/generations/ (so `genimg history` still sees them) and
can be dragged back onto the canvas to iterate.

Ported from a Claude Design mock (vanilla JS, no framework). Stdlib + Pillow only
(Pillow is already a genimg dependency, used here just to read source dimensions).
"""
from __future__ import annotations

import base64
import errno
import ipaddress
import json
import os
import secrets
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from http import server as _http_server
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from . import discovery, metadata, providers, registry
from .auth import resolve as auth_resolve
from .providers.base import ALL_ASPECTS, _res_order

# Extensions we treat as loadable source images.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _aspect_sort(aspects) -> list[str]:
  """Wide → square → tall, the order the studio's aspect picker expects."""
  def ratio(a: str) -> float:
    w, h = a.split(":")
    return int(w) / int(h)
  return sorted(aspects, key=ratio, reverse=True)


def _studio_models() -> list[dict]:
  """Every image-editable model in the registry, as dropdown entries.
  Built from the registry and each provider's declared capabilities so the studio never
  drifts out of sync with what genimg supports. Ordered by provider, best quality first."""
  out: list[dict] = []
  order = {p.name: p.order for p in providers.all_providers()}
  for alias, spec in registry.all_canonical().items():
    provider = providers.get(spec.provider)
    caps = provider.capabilities(spec.model_id)
    label = (f"{alias} · {provider.label}" if provider.runtime_selects_model
             else f"{alias} · {spec.model_id.replace('-preview', '')}")
    out.append({
      "alias": alias,
      "label": label,
      "modelId": spec.model_id,
      "provider": spec.provider,
      "rank": spec.quality_rank,
      "qualityOptions": list(caps.qualities),
      "resolutionOptions": sorted(caps.resolutions, key=_res_order),
      "resolutionOptionsByAspect": caps.resolution_options_by_aspect(),
      "aspectOptions": _aspect_sort(caps.aspect_ratios),
      "thinkingOptions": list(caps.thinking_levels),
      "prices": provider.price_table(spec.model_id),
      "subscription": provider.billing == "subscription",
    })
  out.sort(key=lambda m: (order.get(m["provider"], 99), -m["rank"], m["alias"]))
  return out


# Models offered in the studio dropdown (alias sent to genimg + display label + provider/model_id).
STUDIO_MODELS = _studio_models()

# Provider/region-level failures: the whole cohort is unreachable (bad/missing creds, wrong region).
_UNREACHABLE = {"auth", "403", "404", "error"}


def available_models(cache: dict | None, provider_auth: dict | None = None) -> list[dict]:
  """Annotate every Studio model with auth/probe availability; never hide an option.

  Provider auth is conclusive enough to disable a whole cohort. A missing OpenAI catalog entry
  is disabled individually, but a listed Azure base model is only advertised capacity until a
  generation succeeds. Vertex model listing is known to under-report Model Garden models, so
  "missing" is kept selectable. Provider/region request failures disable only affected entries.
  """
  probes = (cache or {}).get("probes") or {}
  provider_auth = provider_auth or {name: info.as_dict() for name, info in auth_resolve.all_info().items()}
  out: list[dict] = []
  for m in STUDIO_MODELS:
    probe = probes.get(m["alias"]) or {}
    status = probe.get("status")
    auth = provider_auth.get(m["provider"]) or {}
    enabled = bool(auth.get("ok"))
    availability = "available" if status == "working" else "unknown"
    reason = "generation verified" if status == "working" else ""
    if status == "listed":
      availability = "listed"
      reason = "listed by provider; generation not verified"
    if m["subscription"] and enabled:
      status = "ready"  # Login is checked live; do not reuse an old logged-out cache.
      availability = "ready"
      reason = "the provider selects the image model and size; aspect ratio is a prompt request"
    if not enabled:
      availability = "unavailable"
      reason = str(auth.get("hint") or f"{m['provider']} auth is not configured")
    elif status == "missing" and providers.get(m["provider"]).listing_is_exhaustive:
      enabled = False
      availability = "unavailable"
      reason = f"not available on this {providers.get(m['provider']).label} endpoint"
    elif status in _UNREACHABLE:
      enabled = False
      availability = "unavailable"
      reason = str(probe.get("detail") or f"provider probe failed ({status})")
    elif status == "missing":
      availability = "unconfirmed"
      reason = "not listed by the provider; it may still generate"
    elif status is None:
      reason = "not probed yet"
    out.append({**m, "enabled": enabled, "availability": availability,
                "probeStatus": status, "reason": reason})
  return out
DEFAULT_PROMPT = (
  "- handwritten marks = edit instructions, don't copy them literally\n"
  "- keep un-annotated parts unchanged\n"
  "- fresh sketch = render it faithfully\n"
  "- output: clean flat-vector diagram, white background, sans-serif labels"
)
PROMPT_STARTERS = [
  {"label": "Create", "prompt": "Create a single clean image of "},
  {"label": "Diagram", "prompt": "Create a clean flat-vector diagram of "},
  {"label": "Polish", "prompt": (
    "Polish this image while keeping its composition and content unchanged. "
    "Improve spacing, alignment, line consistency, and legibility."
  )},
]


def discover_images(paths: list[Path]) -> list[Path]:
  """Expand CLI paths into a sorted, de-duplicated list of image files.

  Directories are globbed (non-recursively) for IMAGE_EXTS; files are kept if
  their extension is an image; everything else is ignored.
  """
  found: list[Path] = []
  seen: set[Path] = set()
  for p in paths:
    p = p.expanduser()
    candidates: list[Path]
    if p.is_dir():
      candidates = sorted(c for c in p.iterdir() if c.is_file() and c.suffix.lower() in IMAGE_EXTS)
    elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
      candidates = [p]
    else:
      candidates = []
    for c in candidates:
      rp = c.resolve()
      if rp not in seen:
        seen.add(rp)
        found.append(rp)
  return found


def _nearest_aspect(w: int, h: int, aspect_options: list[str]) -> str:
  """Snap the flattened canvas to the closest of the model's declared aspect ratios."""
  ratio = (w / h) if h else 1.0
  ratios = {
    aspect: int(aspect.split(":", 1)[0]) / int(aspect.split(":", 1)[1])
    for aspect in aspect_options
  }
  return min(ratios, key=lambda aspect: abs(ratios[aspect] - ratio))


def _provider_of(model: str) -> str:
  """Provider name for a studio model alias (offline; falls back to a prefix heuristic)."""
  try:
    return registry.resolve(model)[1].provider
  except Exception:
    return "openai" if ("oai" in model or "gpt-image" in model) else "google"


def pick_size(provider: str, w: int, h: int, resolution: str | None,
              aspect: str | None = None,
              aspect_options: list[str] | None = None,
              model_id: str | None = None) -> tuple[str | None, str | None]:
  """Choose a valid (aspect, resolution) for the flattened composite, from the provider's
  declared capabilities.

  - Free-size providers (Gemini) pass the selected image_size when the model exposes one.
  - Table-size providers (OpenAI) snap unsupported aspect/resolution pairs to 2K, or to the
    first valid size when the model has no 2K (GPT Image 1.x).
  - Runtime-selected providers (Codex) pass only a chosen aspect, as a prompt request; Auto
    (aspect None) sends no aspect, as the CLI does without -a.
  """
  prov = providers.get(provider)
  caps = prov.capabilities(model_id or "")
  if caps.sizes:
    by_aspect = caps.resolution_options_by_aspect()
    aspect = aspect if aspect in by_aspect else _nearest_aspect(w, h, list(by_aspect))
    valid = by_aspect[aspect]
    requested = resolution or caps.default_resolution or "1K"
    if requested not in valid:
      requested = "2K" if "2K" in valid else valid[0]
    return aspect, requested
  aspects = aspect_options or _aspect_sort(caps.aspect_ratios if model_id is not None else ALL_ASPECTS)
  if prov.runtime_selects_model:
    return (aspect if aspect in aspects else None), None
  aspect = aspect if aspect in aspects else _nearest_aspect(w, h, aspects)
  if model_id is None:
    return aspect, resolution or None  # unknown model: trust the caller's size
  return aspect, resolution if resolution in caps.resolutions else None


def _genimg_cmd() -> list[str]:
  """Invoke genimg via the SAME interpreter running the studio, so the spawned subprocess is
  always this exact install — never a different/stale `genimg` earlier on PATH."""
  return [sys.executable, "-m", "genimg"]


class _Job:
  __slots__ = ("id", "model", "proc", "out", "log", "started")

  def __init__(self, jid: str, model: str, proc: subprocess.Popen, out: Path, log: Path):
    self.id = jid
    self.model = model
    self.proc = proc
    self.out = out
    self.log = log
    self.started = time.time()


class Studio:
  """Holds session state: source images, the work dir, and running jobs."""

  def __init__(self, sources: list[Path], default_model: str):
    self.sources = sources
    self.default_model = default_model
    self.workdir = Path(metadata.GENIMG_HOME) / "draw_work"
    self.workdir.mkdir(parents=True, exist_ok=True)
    self.gen_dir = Path(metadata.GEN_DIR)
    self.gen_dir.mkdir(parents=True, exist_ok=True)
    self.jobs: dict[str, _Job] = {}
    self.lock = threading.Lock()

  def boot_data(self) -> dict:
    # load_fresh_cache() returns None once the probe cache is older than the refresh interval
    # (5 days). Stale/missing probe data is shown as unknown rather than hiding models.
    provider_auth = {name: info.as_dict() for name, info in auth_resolve.all_info().items()}
    models = available_models(discovery.load_fresh_cache(), provider_auth)
    enabled = [m for m in models if m["enabled"]]
    default = self.default_model if any(
      m["alias"] == self.default_model and m["enabled"] for m in models
    ) else (enabled[0]["alias"] if enabled else models[0]["alias"])
    return {
      "sources": [{"idx": i, "name": p.name} for i, p in enumerate(self.sources)],
      "models": models,
      "providers": {name: {"mode": info.get("mode"), "ok": info.get("ok"),
                           "hint": info.get("hint", ""), "label": providers.get(name).label}
                    for name, info in provider_auth.items()},
      "providerOrder": providers.names(),
      "defaultModel": default,
      "defaultPrompt": DEFAULT_PROMPT,
      "promptStarters": PROMPT_STARTERS,
      "genDir": str(self.gen_dir).replace(str(Path.home()), "~"),
    }

  def history_items(self, limit: int = 80) -> list[dict]:
    """Recent images in ~/.genimg/generations/ (all past genimg output), newest first — the
    'All' history view's import library. Served via the existing /gen/<name> route; each is
    enriched with model + timestamp from its metadata sidecar when available."""
    files = [p for p in self.gen_dir.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:limit]
    meta = metadata.outputs_index()
    out = []
    for p in files:
      info = meta.get(str(p.resolve()), {})
      out.append({"name": p.name, "url": f"/gen/{quote(p.name, safe='')}",
                  "model": info.get("model"), "time": info.get("time")})
    return out

  # ---- job lifecycle ----
  def start_job(self, *, image_b64: str | None, prompt: str, model: str,
                quality: str | None, resolution: str | None, w: int, h: int,
                aspect: str | None = None, thinking: str | None = None) -> str:
    jid = "draw" + secrets.token_hex(6)  # collision-resistant across processes/restarts
    draft = None
    if image_b64:
      png = base64.b64decode(image_b64.split(",", 1)[-1])
      draft = self.workdir / f"{jid}_in.png"
      draft.write_bytes(png)
    out = self.gen_dir / f"draw_{jid}.png"
    logp = self.workdir / f"{jid}.log"

    provider = _provider_of(model)
    model_info = next((item for item in STUDIO_MODELS if item["alias"] == model), None)
    aspect_options = model_info.get("aspectOptions") if model_info else None
    aspect, res = pick_size(provider, w, h, resolution, aspect, aspect_options,
                            model_id=(model_info or {}).get("modelId"))
    # Invoke the hidden `_run` command with OPTIONS FIRST, then `--`, then the prompt — so a
    # prompt beginning with "-" (the default prompt does) is parsed as a positional, not an
    # unknown option. `genimg "- text" ...` otherwise errors with "No such option: -".
    cmd = _genimg_cmd() + ["_run", "-m", model]
    if draft:
      cmd += ["-i", str(draft)]
    if aspect:
      cmd += ["-a", aspect]
    cmd += ["-o", str(out)]
    if res:
      cmd += ["-r", res]
    # Only values this model offers; anything else (a control left over from another model)
    # falls back to the CLI's default rather than failing the job.
    if quality in (model_info or {}).get("qualityOptions", ()):
      cmd += ["-q", quality]
    if thinking in (model_info or {}).get("thinkingOptions", ()):
      cmd += ["--thinking", thinking]
    cmd += ["--", prompt]

    with open(logp, "wb") as logf:  # child dups the fd; parent closes its copy
      proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    with self.lock:
      self.jobs[jid] = _Job(jid, model, proc, out, logp)
    return jid

  def status(self, jid: str) -> dict:
    with self.lock:
      job = self.jobs.get(jid)
    if not job:
      return {"status": "unknown"}
    rc = job.proc.poll()
    if rc is None:
      return {"status": "running", "elapsed": round(time.time() - job.started, 1)}
    if rc == 0 and job.out.exists():
      return {
        "status": "done",
        "elapsed": round(time.time() - job.started, 1),
        "resultUrl": f"/gen/{job.out.name}?t={int(time.time())}",
        "fileName": job.out.name,
      }
    return {"status": "error", "error": _tail(job.log)}


def _tail(path: Path, limit: int = 600) -> str:
  try:
    text = path.read_text(errors="replace")
  except Exception:
    return "generation failed"
  # Strip Rich markup-ish noise; keep the last chunk.
  text = text.strip()
  return text[-limit:] if text else "generation failed"


def _safe_name(name: str) -> str:
  return os.path.basename(unquote(name))


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _host_allowed(host: str | None, bound: tuple[str, int] | None = None) -> bool:
  """Anti-DNS-rebinding guard for ALL routes: the Host header must name an explicit loopback
  address, or exactly the `ADDR:port` the server is bound to (`genimg draw --host ADDR`); on
  port 80 a bare `ADDR` counts too, because browsers omit the default port. A rebinding page
  (Host: attacker.example) is rejected even though it resolves to the server's address, so it
  can't reach /generate or read /history, /gen, /src."""
  if not host:
    return False
  if urlparse("//" + host).hostname in _LOCAL_HOSTS:
    return True
  if bound is None:
    return False
  addr, port = bound
  return host == f"{addr}:{port}" or (port == 80 and host == addr)


def _origin_allowed(origin: str | None, host: str | None) -> bool:
  """CSRF guard for mutating requests. Allow when there's no Origin header (non-browser client
  like curl/tests — not a CSRF vector) or the Origin's host matches the request Host. Blocks a
  drive-by cross-origin POST from a web page while the studio is open on localhost."""
  if not origin:
    return True
  return urlparse(origin).netloc == host


def _boot_json(studio: Studio, boot_data: dict | None = None) -> str:
  """Serialize boot data for inline injection, escaping '<' so a source filename containing
  '<' (or '</script>') can't break out of the inline <script> element."""
  data = studio.boot_data() if boot_data is None else boot_data
  return json.dumps(data).replace("<", "\\u003c")


def _make_handler(studio: Studio):
  boot_data = studio.boot_data()
  models_by_alias = {model["alias"]: model for model in boot_data["models"]}
  page = PAGE.replace("/*__BOOT__*/", _boot_json(studio, boot_data))
  page_bytes = page.encode("utf-8")

  class Handler(_http_server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # keep the console quiet
      pass

    def _send(self, code: int, ctype: str, body: bytes | str):
      if isinstance(body, str):
        body = body.encode("utf-8")
      self.send_response(code)
      self.send_header("Content-Type", ctype)
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      try:
        self.wfile.write(body)
      except (BrokenPipeError, ConnectionResetError):
        pass

    def _send_file(self, path: Path):
      if not path.is_file():
        return self._send(404, "text/plain", b"not found")
      mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif",
      }.get(path.suffix.lower(), "application/octet-stream")
      self._send(200, mime, path.read_bytes())

    def _host_ok(self) -> bool:
      return _host_allowed(self.headers.get("Host"), self.server.server_address[:2])

    def do_GET(self):
      if not self._host_ok():
        return self._send(403, "text/plain", b"forbidden")
      route = urlparse(self.path).path
      if route in ("/", "/index.html"):
        return self._send(200, "text/html; charset=utf-8", page_bytes)
      if route.startswith("/status/"):
        return self._send(200, "application/json", json.dumps(studio.status(route[len("/status/"):])))
      if route == "/history":
        return self._send(200, "application/json", json.dumps({"items": studio.history_items()}))
      if route.startswith("/gen/"):
        return self._send_file(studio.gen_dir / _safe_name(route[len("/gen/"):]))
      if route.startswith("/src/"):
        try:
          idx = int(route[len("/src/"):])
          return self._send_file(studio.sources[idx])
        except (ValueError, IndexError):
          return self._send(404, "text/plain", b"not found")
      return self._send(404, "text/plain", b"not found")

    def do_POST(self):
      if not self._host_ok():
        return self._send(403, "text/plain", b"forbidden")
      route = urlparse(self.path).path
      if route != "/generate":
        return self._send(404, "text/plain", b"not found")
      if not _origin_allowed(self.headers.get("Origin"), self.headers.get("Host")):
        return self._send(403, "application/json", json.dumps({"error": "cross-origin request refused"}))
      length = int(self.headers.get("Content-Length", 0))
      try:
        data = json.loads(self.rfile.read(length) or b"{}")
      except json.JSONDecodeError:
        return self._send(400, "application/json", json.dumps({"error": "bad json"}))
      image = data.get("image") or None
      prompt = (data.get("prompt") or (DEFAULT_PROMPT if image else "")).strip()
      if not image and not prompt:
        return self._send(400, "application/json", json.dumps({"error": "no image or prompt"}))
      model = data.get("model") or studio.default_model
      model_info = models_by_alias.get(model)
      if model_info is None:
        return self._send(400, "application/json", json.dumps({"error": "unknown model"}))
      if not model_info["enabled"]:
        reason = model_info.get("reason") or "model is unavailable"
        return self._send(400, "application/json", json.dumps({"error": reason}))
      try:
        jid = studio.start_job(
          image_b64=image,
          prompt=prompt,
          model=model,
          quality=data.get("quality"),
          resolution=data.get("resolution"),
          aspect=data.get("aspect"),
          thinking=data.get("thinking"),
          w=int(data.get("w") or 1024),
          h=int(data.get("h") or 1024),
        )
      except Exception as e:  # decode / spawn failure → surface to the tray
        return self._send(400, "application/json", json.dumps({"error": f"{type(e).__name__}: {e}"}))
      return self._send(200, "application/json", json.dumps({"job_id": jid}))

  return Handler


class _Server(socketserver.ThreadingMixIn, _http_server.HTTPServer):
  daemon_threads = True
  allow_reuse_address = True


_HOST_HINT = "`tailscale ip -4` or `ipconfig getifaddr en0`"


def _bind_address(host: str) -> ipaddress.IPv4Address:
  """Validate `--host`: one specific IPv4 address. 0.0.0.0 is refused because the Host guard
  allows exactly the bound `ADDR:port`, which a wildcard bind leaves unknowable."""
  try:
    ip = ipaddress.IPv4Address(host)
  except ValueError:
    raise RuntimeError(f"--host needs an IPv4 address, such as the output of {_HOST_HINT}") from None
  if ip.is_unspecified:
    raise RuntimeError(f"--host {host} listens on every network; pass one address from {_HOST_HINT}")
  return ip


def serve(sources: list[Path], *, port: int = 8788, model: str = "gdm:nb2",
          open_browser: bool = True, host: str = "127.0.0.1") -> None:
  """Start the studio server (auto-bumping the port if busy) and block."""
  ip = _bind_address(host)
  studio = Studio(sources, default_model=model)
  handler = _make_handler(studio)
  httpd = None
  chosen = port
  for candidate in range(port, port + 25):
    try:
      httpd = _Server((str(ip), candidate), handler)
      chosen = candidate
      break
    except OSError as e:
      if e.errno == errno.EADDRNOTAVAIL:
        raise RuntimeError(f"{ip} is not an address of this machine; check {_HOST_HINT}") from None
      continue
  if httpd is None:
    raise RuntimeError(f"no free port in {port}..{port + 24}")

  # Only 127.0.0.1 is `localhost`; another 127/8 address must keep its own number in the URL.
  url = f"http://{'localhost' if str(ip) == '127.0.0.1' else ip}:{chosen}"
  n = len(sources)
  print(f"genimg draw studio → {url}  ({n} source image{'' if n == 1 else 's'})", flush=True)
  if not ip.is_loopback:
    print(f"  warning: anyone who can reach {ip}:{chosen} can generate with your credentials "
          "and open every image in ~/.genimg/generations and the images you loaded.", flush=True)
  print("  Ctrl-C to stop.", flush=True)
  if open_browser:
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
  try:
    httpd.serve_forever()
  except KeyboardInterrupt:
    print("\nstopped.", flush=True)
  finally:
    httpd.server_close()


# ────────────────────────────── the page ──────────────────────────────
# Single self-contained HTML page (vanilla JS, no framework). Boot data is
# injected by replacing the /*__BOOT__*/ marker. Ported from the Claude Design
# mock "Draw Studio v2.dc.html".
PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>genimg draw studio</title>
<style>
  html,body{margin:0;padding:0}
  :root{--bg:#f2f2ef;--card:#fff;--panel:#f7f7f5;--border:#e0e0dc;--text:#1c1c1c;--sub:#6f6f6f;--control-sub:#686868;--faint:#9a9a9a;--btn:#f0f0ee;--btnb:#d0d0cb;--accent:#4CAF50;--shadow:0 6px 20px rgba(0,0,0,.08)}
  @media (prefers-color-scheme:dark){:root{--bg:#1a1a1a;--card:#2a2a2a;--panel:#222;--border:#3a3a3a;--text:#fff;--sub:#888;--control-sub:#aaa;--faint:#555;--btn:#333;--btnb:#555;--shadow:0 8px 24px rgba(0,0,0,.35)}}
  *{box-sizing:border-box}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;height:100vh;overflow:hidden}
  #app{display:flex;flex-direction:column;height:100vh}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes toastin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
  ::-webkit-scrollbar{height:8px;width:8px}::-webkit-scrollbar-thumb{background:var(--btnb);border-radius:4px}
  textarea:focus,select:focus{outline:1px solid var(--accent)}
  select{height:36px;background:var(--btn);border:1px solid var(--btnb);color:var(--text);border-radius:8px;padding:0 32px 0 12px;font-size:13px;cursor:pointer}
  [hidden]{display:none!important}
  @media (max-width:520px){#hint .sub{display:none}}
  .tbtn{background:var(--btn);border:1px solid var(--btnb);color:var(--text);width:32px;height:28px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}
  .tbtn.on{border-color:var(--accent);background:var(--btnb)}
  .grp{display:flex;gap:4px;background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:3px}
  .icon{background:none;border:none;color:var(--text);border-radius:5px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}
  .icon:hover{background:var(--btn)}
  .studiohead{background:var(--bg);border-bottom:1px solid var(--border)}
  .headmain{min-height:68px;padding:9px 20px;display:flex;gap:18px;align-items:center}
  .modelslot{width:270px;margin-left:auto;flex:0 0 270px}
  .controlpanel{border-top:1px solid var(--border)}
  .controltoggle{width:100%;height:30px;padding:0 20px;background:transparent;border:0;border-bottom:1px solid var(--border);color:var(--control-sub);font:inherit;font-size:11px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:flex-end;text-align:left}
  .controltoggleinner{width:270px;display:flex;align-items:center;justify-content:flex-end;gap:7px}
  .controltoggle:hover{background:var(--btn);color:var(--text)}
  .controltoggle:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
  .controlpanel.collapsed .controltoggle{border-bottom:0}
  .paramgrid{min-height:62px;padding:8px 20px 10px;display:flex;gap:14px;align-items:flex-end;justify-content:flex-end;flex-wrap:wrap}
  .railicon{width:16px;height:16px;display:block;flex:0 0 16px}
  .trayframe{width:100%;height:100%;min-width:0;min-height:0;display:flex}
  .traycontent{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column}
  .trayrail{width:36px;flex:0 0 36px;min-height:0;padding:9px 0;border:1px solid var(--border);border-radius:10px;background:var(--card);color:var(--sub);cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:10px;box-shadow:var(--shadow)}
  .trayframe.expanded .trayrail{margin-left:8px}
  .trayrail:hover{border-color:var(--btnb);color:var(--text);background:var(--panel)}
  .trayrail:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  .trayraillabel{writing-mode:vertical-rl;font-size:12px;font-weight:600;color:var(--text)}
  #studiogrid>.card{grid-column:1;min-height:0;overflow-y:auto}#splith{grid-column:2}#traycol{grid-column:3}
  #generateBtn{position:sticky;bottom:0}
  .controlfield{display:grid;grid-template-rows:12px 36px;gap:6px;align-items:center;min-width:0}
  .qualityfield,.sizefield{width:max-content}.aspectfield{width:126px}.thinkingfield{width:138px}
  .toplbl{font-size:10px;line-height:12px;color:var(--control-sub);text-transform:uppercase;letter-spacing:.65px;font-weight:600}
  .segctl{display:grid;grid-template-columns:repeat(var(--segments),64px);gap:2px;width:max-content;height:36px;padding:3px;background:var(--btn);border:1px solid var(--btnb);border-radius:8px}
  .segopt{width:64px;height:28px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--control-sub);font:inherit;font-size:11px;font-weight:500;cursor:pointer;white-space:nowrap}
  .segopt:hover:not(.on){color:var(--text);background:color-mix(in srgb,var(--btnb) 55%,transparent)}
  .segopt.on{color:var(--text);background:var(--card);box-shadow:0 1px 2px rgba(0,0,0,.12),inset 0 0 0 1px color-mix(in srgb,var(--btnb) 72%,transparent)}
  .segopt:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  @media (max-width:700px){.headmain{align-items:flex-start;flex-wrap:wrap}.modelslot{width:100%;margin-left:0;flex-basis:100%}.controltoggleinner{width:100%}.paramgrid{justify-content:flex-start}}
  .promptchip.on{border-color:var(--accent)!important;background:color-mix(in srgb,var(--accent) 16%,var(--btn))!important}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow)}
  .job img{width:100%;border-radius:6px;display:block;cursor:zoom-in;background:#fff}
  .job img.g{aspect-ratio:1/1;object-fit:contain}
  .srcthumb{width:100%;border-radius:6px;display:block;cursor:pointer;background:#fff;border:1px solid var(--border)}
  .srcthumb:hover{border-color:var(--accent)}
</style></head>
<body><div id="app"></div>
<script>
const BOOT = /*__BOOT__*/;
(function(){
  "use strict";
  const MM={}; BOOT.models.forEach(m=>{MM[m.alias]=m;});
  const BRUSH_PX = [2,4,6,10,14], BRUSH_DOT=[6,9,12,15,18], PAD=12;
  const SWATCHES = ["#FF3B30","#2979FF","#FF9100","#111111"];
  const S = {
    prompt: BOOT.defaultPrompt, promptExpanded:false,
    model: BOOT.defaultModel, quality:"medium", resolution:"1K", aspect:"auto", thinking:"minimal",
    tool:"pen", color:"#FF3B30", customColor:"#8E24AA", brushLevel:2,
    strokes:[], items:[], selectedId:null,
    view:{x:0,y:0,s:1},
    jobs:[], splitPct:50, trayCollapsed:false, srcCollapsed:false,
    trayScope:"session", trayView:"list", historyItems:[], historyError:"",
    lightbox:null, shortcutsOpen:false, dragActive:false, controlsCollapsed:false,
    sizeControlKey:""
  };
  let _jid=0, _iid=0; const IMGS={}; let cv=null, off=null, cur=null;
  let drawing=false, deleting=false, panning=null, movingId=null, moveOff=null, ro=null;
  const $ = (id)=>document.getElementById(id);
  const esc = (s)=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

  // ---------- static shell ----------
  function shell(){
    const providerNames={}; (BOOT.providerOrder||Object.keys(BOOT.providers||{})).forEach(p=>{providerNames[p]=(BOOT.providers[p]||{}).label||p;});
    const modelOpts = Object.keys(providerNames).map(provider=>{
      const opts=BOOT.models.filter(m=>m.provider===provider).map(m=>{
        const suffix=!m.enabled?" — unavailable":"";
        return `<option value="${esc(m.alias)}"${m.alias===S.model?" selected":""}${m.enabled?"":" disabled"}>${esc(m.label+suffix)}</option>`;
      }).join("");
      return opts?`<optgroup label="${esc(providerNames[provider])}">${opts}</optgroup>`:"";
    }).join("");
    $("app").innerHTML = `
      <header class="studiohead">
        <div class="headmain">
          <div style="display:flex;flex-direction:column;gap:2px;min-width:104px">
            <div style="font-size:16px;font-weight:600;letter-spacing:-.2px">genimg</div>
            <div style="font-size:11px;color:var(--accent);letter-spacing:1px;text-transform:uppercase;font-weight:500">draw studio</div>
          </div>
          <div class="modelslot controlfield">
            <label class="toplbl" for="modelSel">Model</label>
            <select id="modelSel" style="width:100%">${modelOpts}</select>
          </div>
        </div>
        <div id="generationControls" class="controlpanel">
          <button id="controlsToggle" class="controltoggle" type="button" data-act="toggleControls" aria-expanded="true" aria-controls="paramControls"><span class="controltoggleinner"><span>Generation controls</span><span id="controlsIcon" aria-hidden="true"></span></span></button>
          <div id="paramControls" class="paramgrid"></div>
        </div>
      </header>
      <div id="main" style="flex:1;display:flex;min-height:0;padding:16px 20px;gap:10px">
        <div id="srccol" style="display:flex"></div>
        <div id="studiogrid" style="flex:1;display:grid;gap:10px;min-height:0;min-width:0">
          <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;min-width:0">
            <div id="toolbar" style="display:flex;align-items:center;gap:8px 12px;flex-wrap:wrap;row-gap:8px"></div>
            <div id="cvwrap" style="position:relative;background:#fff;border:2px solid var(--border);border-radius:8px;overflow:hidden;flex:1;min-height:340px">
              <canvas id="cv" style="position:absolute;inset:0;width:100%;height:100%;touch-action:none;cursor:crosshair"></canvas>
              <div style="position:absolute;bottom:12px;right:12px;display:flex;gap:2px" class="card">
                <button class="icon" style="width:26px;height:24px;font-size:14px" data-act="zoomOut" title="Zoom out">−</button>
                <button class="icon" id="zoompct" style="min-width:42px;height:24px;font-size:11px;color:var(--sub)" data-act="zoomReset" title="Reset zoom (0)">100%</button>
                <button class="icon" style="width:26px;height:24px;font-size:14px" data-act="zoomIn" title="Zoom in">＋</button>
                <button class="icon" style="width:26px;height:24px;font-size:12px" data-act="shortcuts" title="Shortcuts (?)">?</button>
                <button class="icon" style="width:26px;height:24px" data-act="zoomFit" title="Fit (F)"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg></button>
              </div>
              <div id="hint" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;pointer-events:none;padding:0 24px;text-align:center">
                <div style="font-size:15px;color:var(--faint)">Drop images or start drawing</div>
                <div class="sub" style="font-size:12px;color:var(--faint);max-width:360px;line-height:1.5">scroll to pan · ⌘/ctrl-scroll to zoom · move tool (V) to drag images</div>
              </div>
            </div>
            <div id="promptbox" style="display:flex;flex-direction:column;gap:4px"></div>
            <button id="generateBtn" data-act="generate" style="background:var(--accent);border:none;color:#fff;font-size:15px;font-weight:600;padding:12px;border-radius:10px;cursor:pointer;box-shadow:0 4px 14px rgba(76,175,80,.25)">⚡ Generate <span id="costtext" style="font-weight:400;opacity:.85;font-size:13px"></span></button>
          </div>
          <div id="splith" data-act="split" style="cursor:col-resize;width:14px;margin:0 -4px;display:flex;align-items:center;justify-content:center;touch-action:none"><div style="width:3px;height:56px;background:var(--btnb);border-radius:2px"></div></div>
          <div id="traycol" style="display:flex;flex-direction:column;min-width:0;min-height:0"></div>
        </div>
      </div>
      <div id="overlays"></div>`;
    // static listeners
    cv = $("cv");
    cv.addEventListener("pointerdown", pdown);
    cv.addEventListener("pointermove", pmove);
    cv.addEventListener("pointerup", pup);
    cv.addEventListener("pointerleave", pup);
    cv.addEventListener("wheel", onWheel, {passive:false});
    const wrap = $("cvwrap");
    wrap.addEventListener("dragover", e=>{e.preventDefault(); if(!S.dragActive){S.dragActive=true; wrap.style.borderColor="var(--accent)"; wrap.style.borderStyle="dashed";}});
    wrap.addEventListener("dragleave", ()=>{S.dragActive=false; wrap.style.borderColor="var(--border)"; wrap.style.borderStyle="solid";});
    wrap.addEventListener("drop", onDrop);
    $("modelSel").addEventListener("change", e=>{ S.model=e.target.value; renderTopbar(); renderCost(); });
    ro = new ResizeObserver(sizeCanvas); ro.observe(cv);
    renderTopbar(); renderToolbar(); renderPrompt(); renderCost(); renderTray(); renderSrc(); renderGrid();
    sizeCanvas();
  }

  // ---------- render pieces ----------
  function panelTopIcon(expanded){
    const chevron=expanded?'<path d="m9 15 3-3 3 3"/>':'<path d="m9 12 3 3 3-3"/>';
    return `<svg class="railicon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="3" y1="9" x2="21" y2="9"/>${chevron}</svg>`;
  }
  function panelRightIcon(expanded){
    const chevron=expanded?'<path d="m9 9 3 3-3 3"/>':'<path d="m12 9-3 3 3 3"/>';
    return `<svg class="railicon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="15" y1="3" x2="15" y2="21"/>${chevron}</svg>`;
  }
  function prettyControlValue(v){return v.charAt(0).toUpperCase()+v.slice(1);}
  function segmentedControl(key,label,options,value,fieldClass){
    return `<div class="controlfield ${fieldClass}"><span class="toplbl" id="${key}Label">${esc(label)}</span><div class="segctl" style="--segments:${options.length}" role="radiogroup" aria-labelledby="${key}Label">${options.map(v=>{const on=v===value;return `<button type="button" class="segopt ${on?'on':''}" role="radio" aria-checked="${on}" tabindex="${on?0:-1}" data-seg-key="${key}" data-seg-value="${esc(v)}">${esc(prettyControlValue(v))}</button>`;}).join("")}</div></div>`;
  }
  function controlFocusSnapshot(){
    const active=document.activeElement, controls=$("paramControls");
    if(!active||!controls?.contains(active))return null;
    if(active.id)return {id:active.id};
    if(active.dataset?.segKey)return {key:active.dataset.segKey,value:active.dataset.segValue};
    return null;
  }
  function restoreControlFocus(snapshot){
    if(!snapshot)return;
    const target=snapshot.id?$(snapshot.id):document.querySelector(`[data-seg-key="${snapshot.key}"][data-seg-value="${snapshot.value}"]`);
    target?.focus({preventScroll:true});
  }
  function renderControlsVisibility(){
    const panel=$("generationControls"), controls=$("paramControls"), toggle=$("controlsToggle");
    panel.classList.toggle("collapsed",S.controlsCollapsed);
    controls.hidden=S.controlsCollapsed;
    toggle.setAttribute("aria-expanded",String(!S.controlsCollapsed));
    toggle.title=S.controlsCollapsed?"Show generation controls":"Hide generation controls";
    $("controlsIcon").innerHTML=panelTopIcon(!S.controlsCollapsed);
  }
  function renderTopbar(){
    const focusSnapshot=controlFocusSnapshot();
    $("modelSel").value = S.model;
    const meta=MM[S.model]||{};
    const qualities=meta.qualityOptions||[], resolutions=resolutionOptions(meta), thinking=meta.thinkingOptions||[];
    if(qualities.length&&!qualities.includes(S.quality))S.quality="medium";
    if(resolutions.length&&!resolutions.includes(S.resolution))S.resolution=resolutions.includes("2K")?"2K":resolutions[0];
    if(thinking.length&&!thinking.includes(S.thinking))S.thinking=thinking[0];
    const supportedAspects=meta.aspectOptions||[];
    if(S.aspect!=="auto"&&!supportedAspects.includes(S.aspect))S.aspect="auto";
    const aspects=[["auto","Auto"]].concat(supportedAspects.map(a=>[a,a]));
    S.sizeControlKey=sizeControlKey(meta);
    $("paramControls").innerHTML =
      (qualities.length?segmentedControl("quality","Quality",qualities,S.quality,"qualityfield"):"")+
      (resolutions.length>1?segmentedControl("resolution","Image size",resolutions,S.resolution,"sizefield"):"")+
      `<div class="controlfield aspectfield"><label class="toplbl" for="aspectSel">Aspect ratio</label><select id="aspectSel" aria-label="Aspect ratio" style="width:100%">${aspects.map(a=>`<option value="${a[0]}"${S.aspect===a[0]?" selected":""}>${a[1]}</option>`).join("")}</select></div>`+
      (thinking.length?segmentedControl("thinking","Thinking",thinking,S.thinking,"thinkingfield"):"");
    renderControlsVisibility();
    const optionSets={quality:qualities,resolution:resolutions,thinking};
    const selectSegment=(key,value,focus=false)=>{
      S[key]=value;
      for(const button of document.querySelectorAll(`[data-seg-key="${key}"]`)){
        const on=button.dataset.segValue===value;
        button.classList.toggle("on",on); button.setAttribute("aria-checked",String(on)); button.tabIndex=on?0:-1;
      }
      renderCost();
      if(focus)document.querySelector(`[data-seg-key="${key}"][data-seg-value="${value}"]`)?.focus();
    };
    for(const button of document.querySelectorAll("[data-seg-key]")){
      button.addEventListener("click",()=>selectSegment(button.dataset.segKey,button.dataset.segValue));
      button.addEventListener("keydown",e=>{
        const key=button.dataset.segKey, options=optionSets[key]||[];
        let idx=options.indexOf(S[key]);
        if(e.key==="ArrowRight"||e.key==="ArrowDown")idx=(idx+1)%options.length;
        else if(e.key==="ArrowLeft"||e.key==="ArrowUp")idx=(idx-1+options.length)%options.length;
        else if(e.key==="Home")idx=0;
        else if(e.key==="End")idx=options.length-1;
        else return;
        e.preventDefault(); selectSegment(key,options[idx],true);
      });
    }
    $("aspectSel").addEventListener("change",e=>{S.aspect=e.target.value;renderTopbar();renderCost();});
    const gen=$("generateBtn");
    if(gen){gen.disabled=!meta.enabled;gen.style.opacity=meta.enabled?"1":".45";gen.style.cursor=meta.enabled?"pointer":"not-allowed";gen.title=meta.enabled?"":"Selected model is unavailable";}
    restoreControlFocus(focusSnapshot);
  }
  function renderToolbar(){
    const tool=(t,svg,title)=>`<button class="tbtn ${S.tool===t?'on':''}" data-act="tool" data-tool="${t}" title="${title}">${svg}</button>`;
    const sw = SWATCHES.map(c=>`<button data-act="swatch" data-color="${c}" title="${c}" style="width:22px;height:22px;border-radius:50%;background:${c};border:2px solid ${(S.color===c&&S.tool==='pen')?'var(--text)':'var(--border)'};cursor:pointer;padding:0"></button>`).join("");
    const customSel = (S.tool==='pen'&&S.color===S.customColor);
    $("toolbar").innerHTML = `
      <div class="grp">
        ${tool("move",'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>',"Move / select (V)")}
        ${tool("pen",'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>',"Pen (P)")}
        ${tool("eraser",'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/></svg>',"Eraser (E)")}
        ${tool("strokeDel",'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 5H9l-7 7 7 7h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Z"/><line x1="18" y1="9" x2="12" y2="15"/><line x1="12" y1="9" x2="18" y2="15"/></svg>',"Trace eraser (D) — delete a whole stroke")}
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        ${sw}
        <span style="position:relative;width:22px;height:22px;display:inline-block">
          <span style="position:absolute;inset:0;border-radius:50%;background:conic-gradient(#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00);border:2px solid ${customSel?'var(--text)':'var(--border)'};box-sizing:border-box"></span>
          <input type="color" value="${S.customColor}" data-act="custom" title="Any color" style="position:absolute;inset:0;opacity:0;width:100%;height:100%;cursor:pointer">
        </span>
      </div>
      <div class="grp" style="align-items:center;gap:2px">
        <button class="icon" style="width:24px;height:28px;font-size:14px;opacity:${S.brushLevel===0?.3:1}" data-act="brushDown" title="Thinner ([)">−</button>
        <span title="Brush ${S.brushLevel+1}/5" style="display:inline-block;width:20px;height:20px;position:relative"><span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:${BRUSH_DOT[S.brushLevel]}px;height:${BRUSH_DOT[S.brushLevel]}px;border-radius:50%;background:${S.color}"></span></span>
        <button class="icon" style="width:24px;height:28px;font-size:14px;opacity:${S.brushLevel===4?.3:1}" data-act="brushUp" title="Thicker (])">＋</button>
      </div>
      <div class="grp">
        <button class="tbtn" data-act="undo" title="Undo (⌘Z)">↩</button>
        <button class="tbtn" data-act="clear" title="Clear canvas">✕</button>
      </div>
      <span style="flex:1"></span>
      ${S.selectedId!=null?'<button data-act="removeSel" title="Remove selected image (Delete)" style="background:none;border:none;color:var(--sub);font-size:11px;cursor:pointer">✕ remove selected image</button>':''}`;
    cv.style.cursor = S.tool==="move" ? "default" : "crosshair";
  }
  function renderPrompt(){
    const starters=(BOOT.promptStarters||[]).map((p,i)=>{
      const active=S.prompt.startsWith(p.prompt);
      return `<button class="promptchip ${active?'on':''}" data-act="promptStarter" data-idx="${i}" title="Use this prompt starter" style="background:var(--btn);border:1px solid var(--btnb);color:var(--text);padding:4px 10px;border-radius:999px;font-size:11px;cursor:pointer">${esc(p.label)}</button>`;
    }).join("");
    const defaultActive=S.prompt===BOOT.defaultPrompt;
    $("promptbox").innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><button data-act="togglePrompt" style="background:none;border:none;color:var(--sub);font-size:12px;cursor:pointer;padding:0;text-align:left;margin-right:4px">${S.promptExpanded?"▴ hide prompt":"▸ view or edit prompt"}</button><span style="font-size:10px;color:var(--faint);text-transform:uppercase;letter-spacing:.5px">Start with</span>${starters}<button class="promptchip ${defaultActive?'on':''}" data-act="promptDefault" title="Restore the default annotation instructions" style="background:var(--btn);border:1px solid var(--btnb);color:var(--text);padding:4px 10px;border-radius:999px;font-size:11px;cursor:pointer">Default</button></div>
      ${S.promptExpanded?`<textarea id="promptta" rows="5" spellcheck="false" placeholder="Describe the image you want…" style="background:var(--panel);border:1px solid var(--border);border-radius:12px;color:var(--text);font-size:13px;line-height:1.6;padding:9px 14px;font-family:inherit;width:100%;resize:vertical">${esc(S.prompt)}</textarea>`:""}`;
    const ta = $("promptta");
    if (ta) ta.addEventListener("input", e=>{ S.prompt = e.target.value; updatePromptChipState(); });
  }
  function updatePromptChipState(){
    for(const button of document.querySelectorAll('[data-act="promptStarter"]')){
      const starter=(BOOT.promptStarters||[])[parseInt(button.dataset.idx,10)];
      button.classList.toggle("on",Boolean(starter&&S.prompt.startsWith(starter.prompt)));
    }
    document.querySelector('[data-act="promptDefault"]')?.classList.toggle("on",S.prompt===BOOT.defaultPrompt);
  }
  function renderCost(){ const el=$("costtext"); if(el) el.textContent = "· " + costEstimate(); }
  function nearestAspect(w,h,aspects){const options=aspects&&aspects.length?aspects:["1:1"];const r=h?w/h:1;let best=options[0],bd=1e9;for(const a of options){const parts=a.split(":").map(Number),ar=parts[0]/parts[1],d=Math.abs(ar-r);if(d<bd){bd=d;best=a;}}return best;}
  function renderGrid(){
    const g = $("studiogrid");
    if (S.trayCollapsed) g.style.gridTemplateColumns = "1fr 0 36px";
    else g.style.gridTemplateColumns = `minmax(280px,${S.splitPct}%) 14px minmax(220px,1fr)`;
    $("splith").style.display = S.trayCollapsed ? "none" : "flex";
  }
  function renderSrc(){
    const col = $("srccol");
    if (!BOOT.sources.length){ col.style.display="none"; return; }
    col.style.display="flex";
    if (S.srcCollapsed){
      col.innerHTML = `<button class="card" data-act="toggleSrc" title="Show source images" style="width:44px;display:flex;flex-direction:column;align-items:center;gap:10px;padding:14px 0;color:var(--sub);cursor:pointer;border:1px solid var(--border)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="9" y1="3" x2="9" y2="21"/></svg><span style="writing-mode:vertical-rl;font-size:12px;font-weight:600;color:var(--text)">Sources · ${BOOT.sources.length}</span></button>`;
      return;
    }
    const thumbs = BOOT.sources.map(s=>`<div><img class="srcthumb" src="/src/${s.idx}" title="Click to load · drag onto canvas" data-act="srcLoad" data-drag="src" data-idx="${s.idx}" draggable="true"><div style="font-size:10px;color:var(--sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px">${esc(s.name)}</div></div>`).join("");
    col.innerHTML = `<div style="width:158px;display:flex;flex-direction:column;gap:8px;min-height:0">
      <div style="display:flex;align-items:center;gap:6px">
        <span style="font-size:13px;font-weight:600;flex:1">Sources</span>
        <button class="icon" data-act="toggleSrc" title="Collapse" style="width:22px;height:22px;color:var(--sub)"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="9" y1="3" x2="9" y2="21"/></svg></button>
      </div>
      <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding-right:2px">${thumbs}</div>
    </div>`;
  }
  async function loadHistory(){
    try{ const d=await apiJson("/history"); S.historyItems=d.items||[]; S.historyError=""; }
    catch(e){ S.historyItems=[]; S.historyError=e.message||String(e); }
    renderTray();
  }
  // Items for the Generated panel: session jobs, or (scope=all) in-flight jobs + the whole on-disk
  // history. Disk already holds completed session outputs, so drop done jobs to dedup.
  function trayItems(){
    const jobs=S.jobs.slice().sort((a,b)=>b.createdAt-a.createdAt);
    if(S.trayScope==="session")
      return jobs.map(j=>({status:j.status,id:j.id,url:j.resultUrl,fileName:j.fileName,model:j.model,elapsed:j.elapsed,error:j.error,session:true}));
    const live=jobs.filter(j=>j.status!=="done").map(j=>({status:j.status,id:j.id,model:j.model,elapsed:j.elapsed,error:j.error,session:true}));
    const hist=(S.historyItems||[]).map(h=>({status:"done",url:h.url,fileName:h.name,model:h.model,time:h.time,session:false}));
    return live.concat(hist);
  }
  function statusCard(i){
    if(i.status==="queued") return `<div class="card job" style="padding:10px"><div style="display:flex;align-items:center;gap:10px"><span style="width:18px;height:18px;border-radius:50%;border:2px dashed var(--btnb)"></span><span style="font-size:12px;color:var(--sub)">${esc(i.model||"")} · queued…</span></div></div>`;
    if(i.status==="running") return `<div class="card job" style="padding:10px"><div style="display:flex;align-items:center;gap:10px"><span style="width:18px;height:18px;border-radius:50%;border:2px solid var(--btnb);border-top-color:var(--accent);animation:spin 1s linear infinite"></span><span style="font-size:12px;color:var(--sub)">${esc(i.model||"")} · generating · <span data-elapsed="${i.id}">${Math.round(i.elapsed||0)}s</span></span></div></div>`;
    return `<div class="card job" style="padding:10px;border-color:rgba(255,107,107,.45)"><div style="display:flex;align-items:center;gap:8px"><span style="color:#ff6b6b;font-size:13px">⚠</span><span style="font-size:12px;color:#ff6b6b;font-weight:500;flex:1">generation failed</span><button data-act="retry" data-id="${i.id}" style="background:var(--btn);border:1px solid var(--btnb);color:var(--text);padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer">Retry</button></div><div style="font-size:11px;color:var(--sub);line-height:1.4;margin-top:6px;max-height:80px;overflow:auto;white-space:pre-wrap">${esc((i.error||"").slice(-240))}</div></div>`;
  }
  function rightMeta(i){
    if(i.session) return esc(i.model||"")+" · "+Math.round(i.elapsed||0)+"s";
    const parts=[]; if(i.model)parts.push(esc(i.model)); if(i.time)parts.push(esc((""+i.time).slice(0,16).replace("T"," ")));
    return parts.join(" · ");
  }
  function thumb(i,grid){ return `<img class="${grid?'g':''}" src="${esc(i.url)}" data-act="open" data-url="${esc(i.url)}" data-drag="img" draggable="true" title="${esc(i.fileName||'')} — click to enlarge · drag onto canvas">`; }
  function tweakBtn(i,compact){ return `<button data-act="tweak" data-url="${esc(i.url)}" title="Put on canvas to annotate" style="background:var(--btn);border:1px solid var(--btnb);color:var(--text);${compact?'width:22px;height:20px;padding:0':'padding:4px 12px'};font-size:11px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0">✎${compact?'':' Tweak'}</button>`; }
  function doneListCard(i){
    return `<div class="card job" style="padding:10px"><div style="display:flex;flex-direction:column;gap:8px">${thumb(i)}<div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--sub)">${i.session?'<span style="color:var(--accent)">✓ saved</span>':''}<span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(i.fileName||"")}</span><span style="white-space:nowrap">${rightMeta(i)}</span>${tweakBtn(i,false)}</div></div></div>`;
  }
  function doneGridCard(i){
    // Single-line footer — the file names are opaque ids, so we skip them in grid (still on
    // hover via the thumbnail title, and shown in list view). Just model + date/time + Tweak.
    return `<div class="card job" style="padding:6px;display:flex;flex-direction:column;gap:5px">${thumb(i,true)}<div style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--sub)"><span style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${i.session?'<span style="color:var(--accent)">✓ </span>':''}${rightMeta(i)}</span>${tweakBtn(i,true)}</div></div>`;
  }
  function renderTray(){
    const col = $("traycol");
    if (S.trayCollapsed){
      col.innerHTML = `<div class="trayframe"><button class="trayrail" data-act="toggleTray" title="Show generated images" aria-label="Show generated images">${panelRightIcon(false)}<span class="trayraillabel">Generated${S.jobs.length?" · "+S.jobs.length:""}</span></button></div>`;
      return;
    }
    const items=trayItems();
    const statusHtml=items.filter(i=>i.status!=="done").map(statusCard).join("");
    const done=items.filter(i=>i.status==="done");
    let doneHtml="";
    if(done.length){
      doneHtml = S.trayView==="grid"
        ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;align-content:start">${done.map(doneGridCard).join("")}</div>`
        : `<div style="display:flex;flex-direction:column;gap:10px">${done.map(doneListCard).join("")}</div>`;
    }
    const empty = !statusHtml && !done.length;
    const emptyMsg = S.trayScope==="all"
      ? (S.historyError?esc(S.historyError):"No generations yet.<br>Results save to ~/.genimg/generations/.")
      : "Describe or draw, then hit ⚡ Generate.<br>Results appear here and save automatically.";
    const body = empty
      ? `<div style="flex:1;border:1px dashed var(--btnb);border-radius:12px;display:flex;align-items:center;justify-content:center;padding:24px;font-size:13px;color:var(--faint);text-align:center;line-height:1.6">${emptyMsg}</div>`
      : statusHtml + doneHtml;
    const seg=(label,val)=>`<button data-act="trayScope" data-scope="${val}" style="background:${S.trayScope===val?'var(--btnb)':'transparent'};border:none;color:var(--text);height:24px;padding:0 10px;border-radius:6px;font-size:11px;cursor:pointer;display:flex;align-items:center">${label}</button>`;
    const vbtn=(val,svg,title)=>`<button data-act="trayView" data-view="${val}" title="${title}" style="background:${S.trayView===val?'var(--btnb)':'transparent'};border:none;color:var(--text);width:26px;height:24px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0">${svg}</button>`;
    const listIco='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>';
    const gridIco='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>';
    col.innerHTML = `<div class="trayframe expanded">
      <div class="traycontent">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
          <span style="font-size:13px;font-weight:600">Generated</span>
          <span style="font-size:11px;color:var(--sub);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(BOOT.genDir||'')}">${esc(BOOT.genDir||"~/.genimg/generations/")}</span>
          <div class="grp" style="padding:2px;gap:2px" title="Session = this run · All = your whole ~/.genimg history">${seg("Session","session")}${seg("All","all")}</div>
          <div class="grp" style="padding:2px;gap:2px">${vbtn("list",listIco,"List view")}${vbtn("grid",gridIco,"Grid view")}</div>
        </div>
        <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;min-height:0">${body}</div>
      </div>
      <button class="trayrail" data-act="toggleTray" title="Hide generated images" aria-label="Hide generated images">${panelRightIcon(true)}</button>
    </div>`;
  }
  function renderOverlays(){
    const parts=[];
    if (S.toast) parts.push(`<div style="position:fixed;bottom:20px;right:20px;background:var(--accent);color:#fff;padding:12px 24px;border-radius:8px;z-index:1000;font-size:14px;box-shadow:0 8px 24px rgba(0,0,0,.4);animation:toastin .25s ease">✓ ${esc(S.toast)}</div>`);
    if (S.shortcutsOpen){
      const rows=[["V","move / select"],["P","pen"],["E","eraser"],["D","trace eraser — delete a stroke"],["[ ]","brush size"],["⌘Z","undo"],["delete","remove selected image"],["scroll","pan"],["⌘/ctrl-scroll","zoom at cursor"],["0","reset zoom"],["F","fit content"],["?","this sheet"]];
      parts.push(`<div data-act="closeShortcuts" style="position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:950;display:flex;align-items:center;justify-content:center"><div class="card" style="padding:20px 24px;min-width:340px"><div style="display:flex;align-items:center;gap:10px;margin-bottom:14px"><span style="font-size:14px;font-weight:600;flex:1">Keyboard shortcuts</span><span style="font-size:11px;color:var(--faint)">? toggle · esc close</span></div><div style="display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:13px">${rows.map(r=>`<span style="background:var(--btn);border:1px solid var(--btnb);border-radius:5px;padding:2px 8px;font-family:ui-monospace,Menlo,monospace;text-align:center">${esc(r[0])}</span><span style="color:var(--sub);align-self:center">${esc(r[1])}</span>`).join("")}</div></div></div>`);
    }
    if (S.lightbox) parts.push(`<div data-act="closeLightbox" style="position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:900;display:flex;align-items:center;justify-content:center;cursor:zoom-out"><div style="width:82vw;height:82vh;border-radius:12px;background:#fff url('${S.lightbox}') center/contain no-repeat;box-shadow:0 24px 64px rgba(0,0,0,.6)"></div></div>`);
    $("overlays").innerHTML = parts.join("");
  }
  function toast(m){ S.toast=m; renderOverlays(); clearTimeout(toast._t); toast._t=setTimeout(()=>{S.toast="";renderOverlays();},2800); }

  // ---------- cost (mirrors genimg cost.py) ----------
  function selectedAspect(){
    if(S.aspect!=="auto")return S.aspect;
    const b=contentBounds();
    const aspects=(MM[S.model]||{}).aspectOptions||["1:1"];
    return b?nearestAspect((b[2]-b[0])+PAD*2,(b[3]-b[1])+PAD*2,aspects):"1:1";
  }
  function resolutionOptions(meta=MM[S.model]||{}){
    const all=meta.resolutionOptions||[], byAspect=meta.resolutionOptionsByAspect||{};
    return byAspect[selectedAspect()]||all;
  }
  function sizeControlKey(meta=MM[S.model]||{}){
    const byAspect=meta.resolutionOptionsByAspect||{}, options=resolutionOptions(meta);
    return (Object.keys(byAspect).length?selectedAspect()+"|":"")+options.join(",");
  }
  function selectedResolution(){
    const options=resolutionOptions();
    if(!options.length)return null;
    if(options.includes(S.resolution))return S.resolution;
    return options.includes("2K")?"2K":options[0];
  }
  function effectiveResolution(){
    const meta=MM[S.model]||{}, byAspect=meta.resolutionOptionsByAspect||{};
    if(!Object.keys(byAspect).length)return selectedResolution()||"1K";
    const valid=byAspect[selectedAspect()]||[];
    return valid.includes(S.resolution)?S.resolution:"2K";
  }
  const providerLabel=(p)=>((BOOT.providers||{})[p]||{}).label;
  function costEstimate(){
    const meta=MM[S.model]||{};
    if (meta.subscription) return (providerLabel(meta.provider)||"Subscription")+" · model/size automatic";
    // prices: quality ("" when n/a) → resolution ("" when n/a) → USD, built server-side per model;
    // a "resolution|aspect" key overrides the default-aspect figure where size changes the price.
    const byQ=meta.prices||{}, row=byQ[(meta.qualityOptions||[]).length?S.quality:""]||{};
    const res=(meta.resolutionOptions||[]).length?effectiveResolution():"";
    let usd=row[res+"|"+selectedAspect()]; if(usd==null) usd=row[res]; if(usd==null) usd=row["1K"]; if(usd==null) usd=row[""];
    if(usd==null) return "cost unknown";
    return "~$"+usd.toFixed(3).replace(/0+$/,"").replace(/\.$/,".0");
  }

  // ---------- canvas world ----------
  function sizeCanvas(){
    if(!cv) return;
    const dpr=window.devicePixelRatio||1;
    const w=Math.max(1,Math.round(cv.clientWidth*dpr)), h=Math.max(1,Math.round(cv.clientHeight*dpr));
    if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h;}
    redraw();
  }
  function onWheel(e){
    e.preventDefault(); const v=S.view;
    if(e.ctrlKey||e.metaKey){
      const r=cv.getBoundingClientRect(), mx=e.clientX-r.left, my=e.clientY-r.top;
      const ns=Math.min(8,Math.max(.15,v.s*Math.exp(-e.deltaY*.0022))), k=ns/v.s;
      S.view={s:ns,x:mx-(mx-v.x)*k,y:my-(my-v.y)*k};
    } else { S.view={...v,x:v.x-e.deltaX,y:v.y-e.deltaY}; }
    updateZoom(); redraw();
  }
  function zoomAt(f){
    const v=S.view, mx=cv.clientWidth/2, my=cv.clientHeight/2;
    const ns=Math.min(8,Math.max(.15,v.s*f)), k=ns/v.s;
    S.view={s:ns,x:mx-(mx-v.x)*k,y:my-(my-v.y)*k}; updateZoom(); redraw();
  }
  function contentBounds(){
    let x1=Infinity,y1=Infinity,x2=-Infinity,y2=-Infinity;
    for(const it of S.items){x1=Math.min(x1,it.x);y1=Math.min(y1,it.y);x2=Math.max(x2,it.x+it.w);y2=Math.max(y2,it.y+it.h);}
    // Expand strokes by their radius so edge marks aren't clipped and a perfectly
    // vertical/horizontal stroke still has non-zero extent (won't read as empty).
    for(const st of S.strokes) if(!st.erase){const r=Math.max(1,st.size); for(const p of st.pts){x1=Math.min(x1,p[0]-r);y1=Math.min(y1,p[1]-r);x2=Math.max(x2,p[0]+r);y2=Math.max(y2,p[1]+r);}}
    return x1===Infinity?null:[x1,y1,x2,y2];
  }
  function zoomFit(){
    const b=contentBounds();
    if(!b){S.view={x:0,y:0,s:1};updateZoom();redraw();return;}
    const m=48, s=Math.min(8,Math.max(.15,Math.min((cv.clientWidth-m*2)/(b[2]-b[0]),(cv.clientHeight-m*2)/(b[3]-b[1]))));
    S.view={s,x:(cv.clientWidth-(b[0]+b[2])*s)/2,y:(cv.clientHeight-(b[1]+b[3])*s)/2}; updateZoom(); redraw();
  }
  function updateZoom(){ const z=$("zoompct"); if(z) z.textContent=Math.round(S.view.s*100)+"%"; }
  function toWorld(e){ const r=cv.getBoundingClientRect(), v=S.view; return [((e.clientX-r.left)-v.x)/v.s, ((e.clientY-r.top)-v.y)/v.s]; }
  function hitItem(p){ for(let i=S.items.length-1;i>=0;i--){const it=S.items[i]; if(p[0]>=it.x&&p[0]<=it.x+it.w&&p[1]>=it.y&&p[1]<=it.y+it.h) return it;} return null; }
  function distToStroke(p,st){ let best=Infinity; const pts=st.pts; for(let i=0;i<pts.length-1;i++){const[x1,y1]=pts[i],[x2,y2]=pts[i+1],dx=x2-x1,dy=y2-y1,L2=dx*dx+dy*dy; let t=L2?((p[0]-x1)*dx+(p[1]-y1)*dy)/L2:0; t=Math.max(0,Math.min(1,t)); const ex=x1+dx*t-p[0],ey=y1+dy*t-p[1]; best=Math.min(best,ex*ex+ey*ey);} return Math.sqrt(best); }
  function deleteAt(p){ const thr=12/S.view.s; const i=S.strokes.findIndex(st=>!st.erase&&distToStroke(p,st)<=Math.max(thr,st.size*2)); if(i>=0){S.strokes.splice(i,1);redraw();} }
  function pdown(e){
    e.target.setPointerCapture(e.pointerId); const p=toWorld(e), v=S.view;
    if(e.button===1||S.tool==="move"){
      const it=e.button===1?null:hitItem(p);
      if(it){movingId=it.id;moveOff=[p[0]-it.x,p[1]-it.y]; if(S.selectedId!==it.id){S.selectedId=it.id;renderToolbar();redraw();}}
      else {panning={sx:e.clientX,sy:e.clientY,vx:v.x,vy:v.y}; if(S.selectedId!=null){S.selectedId=null;renderToolbar();redraw();}}
      return;
    }
    if(S.tool==="strokeDel"){deleting=true;deleteAt(p);return;}
    drawing=true; cur={color:S.color,size:BRUSH_PX[S.brushLevel],erase:S.tool==="eraser",pts:[p]};
    hideHint();
  }
  function pmove(e){
    if(panning){S.view={...S.view,x:panning.vx+(e.clientX-panning.sx),y:panning.vy+(e.clientY-panning.sy)};updateZoom();redraw();return;}
    if(movingId!=null){const p=toWorld(e); const it=S.items.find(i=>i.id===movingId); if(it){it.x=p[0]-moveOff[0];it.y=p[1]-moveOff[1];redraw();} return;}
    if(deleting){deleteAt(toWorld(e));return;}
    if(!drawing||!cur)return; cur.pts.push(toWorld(e)); redraw();
  }
  function pup(){ panning=null;movingId=null; if(deleting){deleting=false;return;} if(!drawing||!cur)return; drawing=false; const c=cur; cur=null; if(c.pts.length<2)c.pts.push([c.pts[0][0]+.5,c.pts[0][1]+.5]); S.strokes.push(c); redraw(); }
  function applyStroke(ctx,st){ ctx.globalCompositeOperation=st.erase?"destination-out":"source-over"; ctx.strokeStyle=st.color; ctx.lineWidth=st.erase?st.size*3:st.size; ctx.lineCap="round"; ctx.lineJoin="round"; }
  function strokePath(ctx,st){ ctx.beginPath(); ctx.moveTo(st.pts[0][0],st.pts[0][1]); for(let i=1;i<st.pts.length;i++)ctx.lineTo(st.pts[i][0],st.pts[i][1]); ctx.stroke(); }
  function redraw(){
    if(!cv)return; const ctx=cv.getContext("2d"), dpr=window.devicePixelRatio||1, v=S.view;
    ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle="#fff"; ctx.fillRect(0,0,cv.width,cv.height);
    const step=28*v.s*dpr;
    if(step>9){ctx.fillStyle="rgba(0,0,0,0.07)"; const ox=((v.x*dpr)%step+step)%step, oy=((v.y*dpr)%step+step)%step; for(let x=ox;x<cv.width;x+=step)for(let y=oy;y<cv.height;y+=step)ctx.fillRect(x,y,2,2);}
    ctx.setTransform(dpr*v.s,0,0,dpr*v.s,dpr*v.x,dpr*v.y);
    for(const it of S.items){const img=IMGS[it.id]; if(img)ctx.drawImage(img,it.x,it.y,it.w,it.h);}
    if(!off)off=document.createElement("canvas");
    if(off.width!==cv.width||off.height!==cv.height){off.width=cv.width;off.height=cv.height;}
    const octx=off.getContext("2d"); octx.setTransform(1,0,0,1,0,0); octx.clearRect(0,0,off.width,off.height);
    octx.setTransform(dpr*v.s,0,0,dpr*v.s,dpr*v.x,dpr*v.y);
    const all=cur?S.strokes.concat([cur]):S.strokes;
    for(const st of all){applyStroke(octx,st);strokePath(octx,st);}
    octx.globalCompositeOperation="source-over";
    ctx.setTransform(1,0,0,1,0,0); ctx.drawImage(off,0,0);
    const sel=S.items.find(it=>it.id===S.selectedId);
    if(sel){ctx.setTransform(dpr*v.s,0,0,dpr*v.s,dpr*v.x,dpr*v.y);ctx.strokeStyle="#4CAF50";ctx.lineWidth=1.5/v.s;ctx.setLineDash([6/v.s,4/v.s]);ctx.strokeRect(sel.x,sel.y,sel.w,sel.h);ctx.setLineDash([]);ctx.setTransform(1,0,0,1,0,0);}
    const resolution=selectedResolution();
    if(sizeControlKey()!==S.sizeControlKey||(resolution&&resolution!==S.resolution)){
      if(resolution)S.resolution=resolution;
      renderTopbar();
    }
    renderCost();  // aspect can change the OpenAI estimate and valid size points
  }
  function hideHint(){ const h=$("hint"); if(h&&(S.items.length||S.strokes.length||cur)) h.style.display="none"; }
  // Drawing tools drop the image selection, so Backspace in Pen mode can't delete the photo.
  function setTool(t){ S.tool=t; if(t!=="move")S.selectedId=null; renderToolbar(); redraw(); }

  // ---------- images ----------
  function addImage(url, at, fit){
    const img=new Image();
    img.onload=()=>{
      const id=++_iid; IMGS[id]=img;
      let w=img.naturalWidth,h=img.naturalHeight; const sc=Math.min(1,640/Math.max(w,h)); w*=sc; h*=sc;
      let cx,cy;
      if(at){cx=at[0];cy=at[1];} else {const v=S.view; cx=cv?(cv.clientWidth/2-v.x)/v.s:0; cy=cv?(cv.clientHeight/2-v.y)/v.s:0;}
      S.items.push({id,url,x:cx-w/2,y:cy-h/2,w,h}); S.selectedId=id; S.tool="move";
      renderToolbar(); hideHint(); if(fit)zoomFit(); else redraw();
    };
    img.src=url;
  }
  function onDrop(e){
    e.preventDefault(); S.dragActive=false; const wrap=$("cvwrap"); wrap.style.borderColor="var(--border)"; wrap.style.borderStyle="solid";
    const at=cv?toWorld(e):null;
    const url=e.dataTransfer&&(e.dataTransfer.getData("text/plain")||e.dataTransfer.getData("text/uri-list"));
    // Only same-origin/data URLs — cross-origin http images would taint the canvas and break toDataURL().
    if(url&&(url.indexOf("data:image/")===0||url.indexOf("/gen/")===0||url.indexOf("/src/")===0)){addImage(url,at);return;}
    const files=(e.dataTransfer&&e.dataTransfer.files)?Array.from(e.dataTransfer.files):[];
    files.filter(f=>f.type.startsWith("image/")).forEach((f,i)=>{const rd=new FileReader();rd.onload=()=>addImage(rd.result,at?[at[0]+i*40,at[1]+i*40]:null);rd.readAsDataURL(f);});
  }
  function hasContent(){ return S.items.length>0||S.strokes.length>0; }
  function loadSource(idx){
    const name=(BOOT.sources[idx]||{}).name||"this image";
    if(hasContent()&&!confirm(`Replace the canvas with ${name}? Your drawing will be lost.`))return;
    S.strokes=[]; S.items=[]; S.selectedId=null; renderToolbar(); addImage("/src/"+idx,null,true);
  }

  const SERVER_UNREACHABLE = "Draw Studio server is no longer reachable. Relaunch `genimg draw`, then Retry.";
  async function apiJson(url,options){
    let r;
    try{r=await fetch(url,options);}
    catch(e){throw new Error(SERVER_UNREACHABLE);}
    let d;
    try{d=await r.json();}
    catch(e){throw new Error("Draw Studio server returned an invalid response (HTTP "+r.status+").");}
    if(!r.ok)throw new Error(d.error||("Draw Studio request failed (HTTP "+r.status+")."));
    return d;
  }

  // ---------- flatten + generate ----------
  function flatten(){
    const b=contentBounds(); if(!b)return null;
    const x1=b[0]-PAD, y1=b[1]-PAD;  // small white margin so strokes/diagrams aren't flush to the edge
    const bw=Math.max(1,(b[2]-b[0])+PAD*2), bh=Math.max(1,(b[3]-b[1])+PAD*2);
    const scale=Math.min(2048,Math.max(bw,bh)*2)/Math.max(bw,bh);
    const c=document.createElement("canvas"); c.width=Math.max(1,Math.round(bw*scale)); c.height=Math.max(1,Math.round(bh*scale));
    const ctx=c.getContext("2d"); ctx.fillStyle="#fff"; ctx.fillRect(0,0,c.width,c.height);
    ctx.setTransform(scale,0,0,scale,-x1*scale,-y1*scale);
    for(const it of S.items){const img=IMGS[it.id]; if(img)ctx.drawImage(img,it.x,it.y,it.w,it.h);}
    const o=document.createElement("canvas"); o.width=c.width; o.height=c.height;
    const octx=o.getContext("2d"); octx.setTransform(scale,0,0,scale,-x1*scale,-y1*scale);
    for(const st of S.strokes){applyStroke(octx,st);strokePath(octx,st);}
    octx.globalCompositeOperation="source-over";
    ctx.setTransform(1,0,0,1,0,0); ctx.drawImage(o,0,0);
    return {url:c.toDataURL("image/png"), w:c.width, h:c.height};
  }
  async function generate(){
    const meta=MM[S.model]||{};
    if(!meta.enabled){toast("Selected model is unavailable");return;}
    let flat=null;
    try{ flat=flatten(); }
    catch(e){ toast("can't export the canvas (a cross-origin image tainted it)"); return; }
    if(!flat&&(!S.prompt.trim()||S.prompt===BOOT.defaultPrompt)){
      S.prompt=""; S.promptExpanded=true; renderPrompt();
      requestAnimationFrame(()=>$("promptta")?.focus());
      toast("Describe the first image to generate"); return;
    }
    try{
      const d=await apiJson("/generate",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({image:flat?flat.url:null,prompt:S.prompt,model:S.model,quality:(meta.qualityOptions||[]).includes(S.quality)?S.quality:null,resolution:selectedResolution(),aspect:S.aspect==="auto"?null:S.aspect,thinking:(meta.thinkingOptions||[]).includes(S.thinking)?S.thinking:null,w:flat?flat.w:1024,h:flat?flat.h:1024})});
      S.jobs.push({id:d.job_id,model:S.model,status:"queued",createdAt:Date.now()});
      if(S.trayCollapsed){S.trayCollapsed=false;renderGrid();}
      renderTray();
    }catch(err){ S.jobs.push({id:"e"+(++_jid),model:S.model,status:"error",error:err.message||String(err),createdAt:Date.now()}); renderTray(); }
  }
  function retry(jid){ const j=S.jobs.find(x=>x.id===jid); const m=j?j.model:S.model; S.model=m; renderTopbar(); renderCost(); generate(); }

  // ---------- poll loop ----------
  setInterval(async ()=>{
    const live=S.jobs.filter(j=>j.status==="queued"||j.status==="running");
    if(!live.length)return;
    let dirty=false;
    await Promise.all(live.map(async j=>{
      try{
        const s=await apiJson("/status/"+j.id); j.pollFailures=0;
        if(s.status==="running"){ if(j.status!=="running")dirty=true; j.status="running"; j.elapsed=s.elapsed; }
        else if(s.status==="done"){ j.status="done"; j.elapsed=s.elapsed; j.resultUrl=s.resultUrl; j.fileName=s.fileName; dirty=true; toast("Saved → ~/.genimg/generations/"+s.fileName); }
        else if(s.status==="error"){ j.status="error"; j.error=s.error; dirty=true; }
        else if(s.status==="unknown"){ j.status="error"; j.error="job lost"; dirty=true; }
      }catch(e){
        j.pollFailures=(j.pollFailures||0)+1;
        if(j.pollFailures>=2){j.status="error";j.error=e.message||String(e);dirty=true;}
      }
    }));
    if(dirty){ if(S.trayScope==="all")loadHistory(); else renderTray(); }
    else for(const j of live){const el=document.querySelector('[data-elapsed="'+j.id+'"]'); if(el)el.textContent=Math.round(j.elapsed||0)+"s";}
  },1000);

  // ---------- event delegation ----------
  document.addEventListener("click",(e)=>{
    const t=e.target.closest("[data-act]"); if(!t)return;
    const a=t.dataset.act;
    if(a==="tool"){setTool(t.dataset.tool);}
    else if(a==="swatch"){S.color=t.dataset.color;setTool("pen");}
    else if(a==="brushDown"){S.brushLevel=Math.max(0,S.brushLevel-1);renderToolbar();}
    else if(a==="brushUp"){S.brushLevel=Math.min(4,S.brushLevel+1);renderToolbar();}
    else if(a==="undo"){if(S.strokes.length){S.strokes.pop();redraw();}}
    else if(a==="clear"){if(hasContent()&&!confirm("Clear the canvas? Your drawing will be lost."))return;S.strokes=[];S.items=[];S.selectedId=null;renderToolbar();redraw();const h=$("hint");if(h)h.style.display="flex";}
    else if(a==="removeSel"){S.items=S.items.filter(it=>it.id!==S.selectedId);S.selectedId=null;renderToolbar();redraw();}
    else if(a==="zoomIn"){zoomAt(1.25);} else if(a==="zoomOut"){zoomAt(.8);}
    else if(a==="zoomReset"){S.view={x:0,y:0,s:1};updateZoom();redraw();} else if(a==="zoomFit"){zoomFit();}
    else if(a==="shortcuts"){S.shortcutsOpen=!S.shortcutsOpen;renderOverlays();}
    else if(a==="closeShortcuts"){S.shortcutsOpen=false;renderOverlays();}
    else if(a==="closeLightbox"){S.lightbox=null;renderOverlays();}
    else if(a==="togglePrompt"){S.promptExpanded=!S.promptExpanded;renderPrompt();}
    else if(a==="promptStarter"){
      const p=(BOOT.promptStarters||[])[parseInt(t.dataset.idx,10)];
      if(p){S.prompt=p.prompt;S.promptExpanded=true;renderPrompt();requestAnimationFrame(()=>{const ta=$("promptta");if(ta){ta.focus();ta.setSelectionRange(ta.value.length,ta.value.length);}});}
    }
    else if(a==="promptDefault"){S.prompt=BOOT.defaultPrompt;S.promptExpanded=true;renderPrompt();requestAnimationFrame(()=>$("promptta")?.focus());}
    else if(a==="toggleControls"){S.controlsCollapsed=!S.controlsCollapsed;renderControlsVisibility();}
    else if(a==="generate"){generate();}
    else if(a==="toggleTray"){S.trayCollapsed=!S.trayCollapsed;renderGrid();renderTray();}
    else if(a==="toggleSrc"){S.srcCollapsed=!S.srcCollapsed;renderSrc();}
    else if(a==="srcLoad"){loadSource(parseInt(t.dataset.idx,10));}
    else if(a==="trayScope"){S.trayScope=t.dataset.scope; if(S.trayScope==="all")loadHistory(); else renderTray();}
    else if(a==="trayView"){S.trayView=t.dataset.view; renderTray();}
    else if(a==="open"){S.lightbox=t.dataset.url;renderOverlays();}
    else if(a==="tweak"){addImage(t.dataset.url);}
    else if(a==="retry"){retry(t.dataset.id);}
  });
  document.addEventListener("change",(e)=>{ if(e.target.dataset&&e.target.dataset.act==="custom"){S.customColor=e.target.value;S.color=e.target.value;setTool("pen");} });
  document.addEventListener("dragstart",(e)=>{ const t=e.target.closest("[data-drag]"); if(!t)return; const url=t.getAttribute("src")||t.dataset.url; if(url){e.dataTransfer.setData("text/plain",url);e.dataTransfer.effectAllowed="copy";} });
  document.addEventListener("pointerdown",(e)=>{
    const t=e.target.closest&&e.target.closest('[data-act="split"]'); if(!t)return;
    e.preventDefault(); const grid=$("studiogrid"), rect=grid.getBoundingClientRect();
    const mv=(ev)=>{let pct=(ev.clientX-rect.left)/rect.width*100;pct=Math.max(28,Math.min(78,pct));S.splitPct=Math.round(pct*10)/10;renderGrid();};
    const up=()=>{window.removeEventListener("pointermove",mv);window.removeEventListener("pointerup",up);};
    window.addEventListener("pointermove",mv);window.addEventListener("pointerup",up);
  });
  window.addEventListener("keydown",(e)=>{
    const tag=(e.target&&e.target.tagName)||""; if(tag==="TEXTAREA"||tag==="INPUT"||tag==="SELECT")return;
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="z"){e.preventDefault();if(S.strokes.length){S.strokes.pop();redraw();}return;}
    if((e.key==="Delete"||e.key==="Backspace")&&S.selectedId!=null){e.preventDefault();S.items=S.items.filter(it=>it.id!==S.selectedId);S.selectedId=null;renderToolbar();redraw();return;}
    if(e.key==="Escape"){S.shortcutsOpen=false;S.lightbox=null;renderOverlays();return;}
    if(e.metaKey||e.ctrlKey||e.altKey)return;
    const k=e.key.toLowerCase();
    if(e.key==="?"){S.shortcutsOpen=!S.shortcutsOpen;renderOverlays();}
    else if(k==="v"){setTool("move");} else if(k==="p"){setTool("pen");}
    else if(k==="e"){setTool("eraser");} else if(k==="d"){setTool("strokeDel");}
    else if(k==="["){S.brushLevel=Math.max(0,S.brushLevel-1);renderToolbar();} else if(k==="]"){S.brushLevel=Math.min(4,S.brushLevel+1);renderToolbar();}
    else if(k==="0"){S.view={x:0,y:0,s:1};updateZoom();redraw();} else if(k==="f"){zoomFit();}
  });
  window.addEventListener("resize",sizeCanvas);

  shell();
})();
</script></body></html>"""
