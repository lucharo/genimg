"""genimg draw — a local "draw studio" web app.

`genimg draw [PATHS...]` starts a stdlib HTTP server that serves a single-page,
Excalidraw-style canvas: drop/annotate images with vector strokes, then hit
Generate. Each Generate flattens the canvas to a PNG and spawns its OWN `genimg`
subprocess in the background (concurrent); the page polls /status until done.
Results land in ~/.genimg/generations/ (so `genimg history` still sees them) and
can be dragged back onto the canvas to iterate.

Ported from a Claude Design mock (vanilla JS, no framework). Stdlib + Pillow only
(Pillow is already a genimg dependency, used here just to read source dimensions).
"""
from __future__ import annotations

import base64
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

from . import cost, discovery, metadata, registry

# Extensions we treat as loadable source images.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _studio_models() -> list[dict]:
  """Every image-editable model in the registry (excludes text-to-image Imagen, which can't take
  -i), as dropdown entries. Built from the registry so the studio never drifts out of sync with
  what genimg supports. Ordered google→openai, best quality first."""
  out: list[dict] = []
  for alias, spec in registry.all_canonical().items():
    if spec.model_id.startswith("imagen-"):
      continue
    out.append({
      "alias": alias,
      "label": f"{alias} · {spec.model_id.replace('-preview', '')}",
      "modelId": spec.model_id,
      "provider": spec.provider,
      "rank": spec.quality_rank,
    })
  order = {"google": 0, "openai": 1}
  out.sort(key=lambda m: (order.get(m["provider"], 9), -m["rank"], m["alias"]))
  return out


# Models offered in the studio dropdown (alias sent to genimg + display label + provider/model_id).
STUDIO_MODELS = _studio_models()

# Provider/region-level failures: the whole cohort is unreachable (bad/missing creds, wrong region).
_UNREACHABLE = {"auth", "403", "404", "error"}


def available_models(cache: dict | None) -> list[dict]:
  """Filter STUDIO_MODELS by a `genimg models` probe cache.

  - OpenAI: keep only listed/working — its list endpoint is authoritative, so "missing" == absent.
  - Google/Vertex: keep unless the provider/region call itself failed; "missing" stays, because
    models.list() under-reports Model Garden models that still generate (discovery.py caveat).
  - No cache, unknown status, or everything filtered out → show all (never an empty dropdown).
  """
  probes = (cache or {}).get("probes") or {}
  if not probes:
    return list(STUDIO_MODELS)
  out: list[dict] = []
  for m in STUDIO_MODELS:
    status = (probes.get(m["alias"]) or {}).get("status")
    if status is None:
      out.append(m)  # not probed → don't hide
    elif m["provider"] == "openai":
      if status in ("listed", "working"):
        out.append(m)
    elif status not in _UNREACHABLE:  # google/vertex: keep listed + missing (unconfirmed)
      out.append(m)
  return out or list(STUDIO_MODELS)
DEFAULT_PROMPT = (
  "- handwritten marks = edit instructions, don't copy them literally\n"
  "- keep un-annotated parts unchanged\n"
  "- fresh sketch = render it faithfully\n"
  "- output: clean flat-vector diagram, white background, sans-serif labels"
)

# Aspect ratio → numeric ratio, for snapping the flattened canvas to a supported aspect.
_ASPECTS = {"1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "9:16": 9 / 16}


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


def _nearest_aspect(w: int, h: int) -> str:
  ratio = (w / h) if h else 1.0
  return min(_ASPECTS, key=lambda a: abs(_ASPECTS[a] - ratio))


def _provider_of(model: str) -> str:
  """openai vs google for a studio model alias (offline; falls back to a prefix heuristic)."""
  try:
    from . import registry
    return registry.resolve(model)[1].provider
  except Exception:
    return "openai" if ("oai" in model or "gpt-image" in model) else "google"


def pick_size(provider: str, w: int, h: int, param: str | None) -> tuple[str, str | None]:
  """Choose a valid (aspect, resolution) for the flattened composite.

  - Gemini honors any aspect at any image_size → aspect from ratio, resolution = the
    selected image_size (param).
  - OpenAI has a constrained size table: 16:9/9:16 need 2K (1K is below the pixel min);
    everything else fits at 1K. Quality is passed separately, so param is ignored here.
  """
  aspect = _nearest_aspect(w, h)
  if provider == "openai":
    resolution = "2K" if aspect in ("16:9", "9:16") else "1K"
  else:
    resolution = param or None
  return aspect, resolution


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
    drop_none = lambda tbl: {k: v for k, v in tbl.items() if k is not None}
    # load_fresh_cache() returns None once the probe cache is older than the refresh interval
    # (5 days) → available_models() then shows ALL models. We never filter on stale data; the
    # user re-enables filtering by running `genimg models`.
    visible = available_models(discovery.load_fresh_cache())
    default = self.default_model if any(m["alias"] == self.default_model for m in visible) else visible[0]["alias"]
    return {
      "sources": [{"idx": i, "name": p.name} for i, p in enumerate(self.sources)],
      "models": [{"alias": m["alias"], "label": m["label"], "modelId": m["modelId"],
                  "provider": m["provider"]} for m in visible],
      "defaultModel": default,
      "defaultPrompt": DEFAULT_PROMPT,
      "genDir": str(self.gen_dir).replace(str(Path.home()), "~"),
      # Real cost tables from cost.py so the client estimate is per-model accurate + stays in sync.
      "costs": {
        "openaiBase": cost._OPENAI_BASE_PER_IMAGE,
        "openaiResMult": drop_none(cost._OPENAI_RESOLUTION_MULT),
        "googlePerImage": {mid: drop_none(tbl) for mid, tbl in cost._GOOGLE_PER_IMAGE.items()},
      },
    }

  def _meta_by_output(self) -> dict[str, dict]:
    """Map each generated file name → its {model, time} from the metadata sidecars, so history
    thumbnails can show what produced them. (Generation *duration* isn't recorded on disk — that's
    only known for this session's own jobs.)"""
    out: dict[str, dict] = {}
    meta_dir = Path(metadata.META_DIR)
    if not meta_dir.exists():
      return out
    # Oldest → newest so a later sidecar writing the same output path wins on collision.
    for f in sorted(meta_dir.glob("*.json"), key=lambda p: p.stat().st_mtime):
      try:
        data = json.loads(f.read_text())
      except (json.JSONDecodeError, OSError):
        continue
      info = {"model": data.get("alias") or data.get("model_id"), "time": data.get("time")}
      workdir = data.get("workdir")
      for o in data.get("outputs", []):
        p = Path(o["path"] if isinstance(o, dict) else o)
        if not p.is_absolute() and workdir:  # resolve against the recorded cwd, not ours
          p = Path(workdir) / p
        out[str(p.resolve())] = info
    return out

  def history_items(self, limit: int = 80) -> list[dict]:
    """Recent images in ~/.genimg/generations/ (all past genimg output), newest first — the
    'All' history view's import library. Served via the existing /gen/<name> route; each is
    enriched with model + timestamp from its metadata sidecar when available."""
    files = [p for p in self.gen_dir.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:limit]
    meta = self._meta_by_output()
    out = []
    for p in files:
      info = meta.get(str(p.resolve()), {})
      out.append({"name": p.name, "url": f"/gen/{quote(p.name, safe='')}",
                  "model": info.get("model"), "time": info.get("time")})
    return out

  # ---- job lifecycle ----
  def start_job(self, *, image_b64: str, prompt: str, model: str,
                quality: str | None, resolution: str | None, w: int, h: int) -> str:
    png = base64.b64decode(image_b64.split(",", 1)[-1])
    jid = "draw" + secrets.token_hex(6)  # collision-resistant across processes/restarts
    draft = self.workdir / f"{jid}_in.png"
    draft.write_bytes(png)
    out = self.gen_dir / f"draw_{jid}.png"
    logp = self.workdir / f"{jid}.log"

    provider = _provider_of(model)
    aspect, res = pick_size(provider, w, h, resolution)
    # Invoke the hidden `_run` command with OPTIONS FIRST, then `--`, then the prompt — so a
    # prompt beginning with "-" (the default prompt does) is parsed as a positional, not an
    # unknown option. `genimg "- text" ...` otherwise errors with "No such option: -".
    cmd = _genimg_cmd() + ["_run", "-m", model, "-i", str(draft), "-a", aspect, "-o", str(out)]
    if res:
      cmd += ["-r", res]
    if provider == "openai" and quality:
      cmd += ["-q", quality]
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


def _host_allowed(host: str | None) -> bool:
  """Anti-DNS-rebinding guard for ALL routes: the Host header must name an explicit loopback
  address. A rebinding page (Host: attacker.example) is rejected even though it resolves to
  127.0.0.1, so it can't reach /generate or read /history, /gen, /src."""
  if not host:
    return False
  return urlparse("//" + host).hostname in _LOCAL_HOSTS


def _origin_allowed(origin: str | None, host: str | None) -> bool:
  """CSRF guard for mutating requests. Allow when there's no Origin header (non-browser client
  like curl/tests — not a CSRF vector) or the Origin's host matches the request Host. Blocks a
  drive-by cross-origin POST from a web page while the studio is open on localhost."""
  if not origin:
    return True
  return urlparse(origin).netloc == host


def _boot_json(studio: Studio) -> str:
  """Serialize boot data for inline injection, escaping '<' so a source filename containing
  '<' (or '</script>') can't break out of the inline <script> element."""
  return json.dumps(studio.boot_data()).replace("<", "\\u003c")


def _make_handler(studio: Studio):
  page = PAGE.replace("/*__BOOT__*/", _boot_json(studio))
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

    def do_GET(self):
      if not _host_allowed(self.headers.get("Host")):
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
      if not _host_allowed(self.headers.get("Host")):
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
      image = data.get("image") or ""
      if not image:
        return self._send(400, "application/json", json.dumps({"error": "no image"}))
      try:
        jid = studio.start_job(
          image_b64=image,
          prompt=(data.get("prompt") or DEFAULT_PROMPT).strip(),
          model=data.get("model") or studio.default_model,
          quality=data.get("quality"),
          resolution=data.get("resolution"),
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


def serve(sources: list[Path], *, port: int = 8788, model: str = "gdm:nb2",
          open_browser: bool = True) -> None:
  """Start the studio server (auto-bumping the port if busy) and block."""
  studio = Studio(sources, default_model=model)
  handler = _make_handler(studio)
  httpd = None
  chosen = port
  for candidate in range(port, port + 25):
    try:
      httpd = _Server(("127.0.0.1", candidate), handler)
      chosen = candidate
      break
    except OSError:
      continue
  if httpd is None:
    raise RuntimeError(f"no free port in {port}..{port + 24}")

  url = f"http://localhost:{chosen}"
  n = len(sources)
  print(f"genimg draw studio → {url}  ({n} source image{'' if n == 1 else 's'})", flush=True)
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
  :root{--bg:#f2f2ef;--card:#fff;--panel:#f7f7f5;--border:#e0e0dc;--text:#1c1c1c;--sub:#6f6f6f;--faint:#9a9a9a;--btn:#f0f0ee;--btnb:#d0d0cb;--accent:#4CAF50;--shadow:0 6px 20px rgba(0,0,0,.08)}
  @media (prefers-color-scheme:dark){:root{--bg:#1a1a1a;--card:#2a2a2a;--panel:#222;--border:#3a3a3a;--text:#fff;--sub:#888;--faint:#555;--btn:#333;--btnb:#555;--shadow:0 8px 24px rgba(0,0,0,.35)}}
  *{box-sizing:border-box}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;height:100vh;overflow:hidden}
  #app{display:flex;flex-direction:column;height:100vh}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes toastin{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
  ::-webkit-scrollbar{height:8px;width:8px}::-webkit-scrollbar-thumb{background:var(--btnb);border-radius:4px}
  textarea:focus,select:focus{outline:1px solid var(--accent)}
  select{background:var(--btn);border:1px solid var(--btnb);color:var(--text);border-radius:8px;padding:7px 32px 7px 12px;font-size:13px;cursor:pointer}
  @media (max-width:520px){#hint .sub{display:none}}
  .tbtn{background:var(--btn);border:1px solid var(--btnb);color:var(--text);width:32px;height:28px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}
  .tbtn.on{border-color:var(--accent);background:var(--btnb)}
  .grp{display:flex;gap:4px;background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:3px}
  .icon{background:none;border:none;color:var(--text);border-radius:5px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}
  .icon:hover{background:var(--btn)}
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
  const MM={}; BOOT.models.forEach(m=>{MM[m.alias]={modelId:m.modelId,provider:m.provider};});
  const BRUSH_PX = [2,4,6,10,14], BRUSH_DOT=[6,9,12,15,18], PAD=12;
  const SWATCHES = ["#FF3B30","#2979FF","#FF9100","#111111"];
  const S = {
    prompt: BOOT.defaultPrompt, promptExpanded:false,
    model: BOOT.defaultModel, quality:"medium", resolution:"1K",
    tool:"pen", color:"#FF3B30", customColor:"#8E24AA", brushLevel:2,
    strokes:[], items:[], selectedId:null,
    view:{x:0,y:0,s:1},
    jobs:[], splitPct:50, trayCollapsed:false, srcCollapsed:false,
    trayScope:"session", trayView:"list", historyItems:[],
    lightbox:null, shortcutsOpen:false, dragActive:false
  };
  let _jid=0, _iid=0; const IMGS={}; let cv=null, off=null, cur=null;
  let drawing=false, deleting=false, panning=null, movingId=null, moveOff=null, ro=null;
  const $ = (id)=>document.getElementById(id);
  const esc = (s)=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

  // ---------- static shell ----------
  function shell(){
    const modelOpts = BOOT.models.map(m=>`<option value="${esc(m.alias)}"${m.alias===S.model?" selected":""}>${esc(m.label)}</option>`).join("");
    $("app").innerHTML = `
      <div style="background:var(--bg);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;gap:16px;align-items:center">
        <div style="display:flex;flex-direction:column;gap:2px;min-width:104px">
          <div style="font-size:16px;font-weight:600;letter-spacing:-.2px">genimg</div>
          <div style="font-size:11px;color:var(--accent);letter-spacing:1px;text-transform:uppercase;font-weight:500">draw studio</div>
        </div>
        <span style="flex:1"></span>
        <select id="modelSel" style="width:250px">${modelOpts}</select>
        <select id="paramSel" style="width:250px"></select>
      </div>
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
            <button data-act="generate" style="background:var(--accent);border:none;color:#fff;font-size:15px;font-weight:600;padding:12px;border-radius:10px;cursor:pointer;box-shadow:0 4px 14px rgba(76,175,80,.25)">⚡ Generate <span id="costtext" style="font-weight:400;opacity:.85;font-size:13px"></span></button>
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
    $("paramSel").addEventListener("change", e=>{ if(isOai()) S.quality=e.target.value; else S.resolution=e.target.value; renderCost(); });
    ro = new ResizeObserver(sizeCanvas); ro.observe(cv);
    renderTopbar(); renderToolbar(); renderPrompt(); renderCost(); renderTray(); renderSrc(); renderGrid();
    sizeCanvas();
  }

  const isOai = ()=> (MM[S.model]||{}).provider==="openai";

  // ---------- render pieces ----------
  function renderTopbar(){
    $("modelSel").value = S.model;
    const sel = $("paramSel");
    const opts = isOai()
      ? [["medium","quality: medium (default)"],["low","quality: low — fastest"],["high","quality: high — 30–90s/image"]]
      : [["1K","image_size: 1K (default)"],["2K","image_size: 2K"],["4K","image_size: 4K"]];
    sel.title = isOai() ? "quality — gpt-image request parameter" : "image_size — Gemini image_config parameter";
    sel.innerHTML = opts.map(o=>`<option value="${o[0]}">${o[1]}</option>`).join("");
    sel.value = isOai()? S.quality : S.resolution;
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
    $("promptbox").innerHTML = `
      <button data-act="togglePrompt" style="background:none;border:none;color:var(--sub);font-size:12px;cursor:pointer;padding:0;text-align:left">${S.promptExpanded?"▴ hide prompt":"▸ view or edit prompt"}</button>
      ${S.promptExpanded?`<textarea id="promptta" rows="5" spellcheck="false" style="background:var(--panel);border:1px solid var(--border);border-radius:12px;color:var(--text);font-size:13px;line-height:1.6;padding:9px 14px;font-family:inherit;width:100%;resize:vertical">${esc(S.prompt)}</textarea>`:""}`;
    const ta = $("promptta");
    if (ta) ta.addEventListener("input", e=>{ S.prompt = e.target.value; });
  }
  function renderCost(){ const el=$("costtext"); if(el) el.textContent = "· " + costEstimate(); }
  function nearestAspect(w,h){const A={"1:1":1,"4:3":4/3,"3:4":3/4,"16:9":16/9,"9:16":9/16};const r=h?w/h:1;let best="1:1",bd=1e9;for(const a in A){const d=Math.abs(A[a]-r);if(d<bd){bd=d;best=a;}}return best;}
  function renderGrid(){
    const g = $("studiogrid");
    if (S.trayCollapsed) g.style.gridTemplateColumns = "1fr 0 44px";
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
    try{ const d=await (await fetch("/history")).json(); S.historyItems=d.items||[]; }catch(e){ S.historyItems=[]; }
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
      col.innerHTML = `<button class="card" data-act="toggleTray" title="Show generated images" style="width:44px;flex:1;display:flex;flex-direction:column;align-items:center;gap:10px;padding:14px 0;color:var(--sub);cursor:pointer;border:1px solid var(--border)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="15" y1="3" x2="15" y2="21"/></svg><span style="writing-mode:vertical-rl;font-size:12px;font-weight:600;color:var(--text)">Generated${S.jobs.length?" · "+S.jobs.length:""}</span></button>`;
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
      ? "No generations yet.<br>Results save to ~/.genimg/generations/."
      : "Draw, then hit ⚡ Generate.<br>Results appear here and save automatically.";
    const body = empty
      ? `<div style="flex:1;border:1px dashed var(--btnb);border-radius:12px;display:flex;align-items:center;justify-content:center;padding:24px;font-size:13px;color:var(--faint);text-align:center;line-height:1.6">${emptyMsg}</div>`
      : statusHtml + doneHtml;
    const seg=(label,val)=>`<button data-act="trayScope" data-scope="${val}" style="background:${S.trayScope===val?'var(--btnb)':'transparent'};border:none;color:var(--text);height:24px;padding:0 10px;border-radius:6px;font-size:11px;cursor:pointer;display:flex;align-items:center">${label}</button>`;
    const vbtn=(val,svg,title)=>`<button data-act="trayView" data-view="${val}" title="${title}" style="background:${S.trayView===val?'var(--btnb)':'transparent'};border:none;color:var(--text);width:26px;height:24px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0">${svg}</button>`;
    const listIco='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>';
    const gridIco='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>';
    col.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
        <span style="font-size:13px;font-weight:600">Generated</span>
        <span style="font-size:11px;color:var(--sub);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(BOOT.genDir||'')}">${esc(BOOT.genDir||"~/.genimg/generations/")}</span>
        <div class="grp" style="padding:2px;gap:2px" title="Session = this run · All = your whole ~/.genimg history">${seg("Session","session")}${seg("All","all")}</div>
        <div class="grp" style="padding:2px;gap:2px">${vbtn("list",listIco,"List view")}${vbtn("grid",gridIco,"Grid view")}</div>
        <button class="icon" data-act="toggleTray" title="Collapse" style="width:22px;height:22px;color:var(--sub)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/><line x1="15" y1="3" x2="15" y2="21"/></svg></button>
      </div>
      <div style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;min-height:0">${body}</div>`;
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
  function costEstimate(){
    const mid=(MM[S.model]||{}).modelId, C=BOOT.costs||{};
    let usd;
    if (isOai()){
      usd = ((C.openaiBase||{})[mid]||{})[S.quality]; if(usd==null) usd=0.053;
      // server forces 2K for 16:9/9:16 (1K is below OpenAI's pixel min) → mirror cost.py's mult
      const b=contentBounds();
      if(b){const a=nearestAspect((b[2]-b[0])+PAD*2,(b[3]-b[1])+PAD*2); if(a==="16:9"||a==="9:16") usd*=((C.openaiResMult||{})["2K"]||2.5);}  // match flatten()'s padded dims
    } else {
      const key=(mid&&mid.endsWith("-preview"))?mid.slice(0,-8):mid; // google table keyed by GA id
      const t=(C.googlePerImage||{})[key]||{};
      usd=t[S.resolution]; if(usd==null)usd=t["1K"]; if(usd==null)usd=0.067;
    }
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
    renderCost();  // aspect can change the OpenAI estimate as content changes
  }
  function hideHint(){ const h=$("hint"); if(h&&(S.items.length||S.strokes.length||cur)) h.style.display="none"; }

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
  function loadSource(idx){ S.strokes=[]; S.items=[]; S.selectedId=null; renderToolbar(); addImage("/src/"+idx,null,true); }

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
    let flat=null;
    try{ flat=flatten(); }
    catch(e){ toast("can't export the canvas (a cross-origin image tainted it)"); return; }
    if(!flat){toast("nothing to generate — draw or drop an image");return;}
    try{
      const r=await fetch("/generate",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({image:flat.url,prompt:S.prompt,model:S.model,quality:S.quality,resolution:S.resolution,w:flat.w,h:flat.h})});
      const d=await r.json();
      if(d.error){ S.jobs.push({id:"e"+(++_jid),model:S.model,status:"error",error:d.error,createdAt:Date.now()}); renderTray(); return; }
      S.jobs.push({id:d.job_id,model:S.model,status:"queued",createdAt:Date.now()});
      if(S.trayCollapsed){S.trayCollapsed=false;renderGrid();}
      renderTray();
    }catch(err){ S.jobs.push({id:"e"+(++_jid),model:S.model,status:"error",error:String(err),createdAt:Date.now()}); renderTray(); }
  }
  function retry(jid){ const j=S.jobs.find(x=>x.id===jid); const m=j?j.model:S.model; S.model=m; generate(); }

  // ---------- poll loop ----------
  setInterval(async ()=>{
    const live=S.jobs.filter(j=>j.status==="queued"||j.status==="running");
    if(!live.length)return;
    let dirty=false;
    await Promise.all(live.map(async j=>{
      try{
        const s=await (await fetch("/status/"+j.id)).json();
        if(s.status==="running"){ if(j.status!=="running")dirty=true; j.status="running"; j.elapsed=s.elapsed; }
        else if(s.status==="done"){ j.status="done"; j.elapsed=s.elapsed; j.resultUrl=s.resultUrl; j.fileName=s.fileName; dirty=true; toast("Saved → ~/.genimg/generations/"+s.fileName); }
        else if(s.status==="error"){ j.status="error"; j.error=s.error; dirty=true; }
        else if(s.status==="unknown"){ j.status="error"; j.error="job lost"; dirty=true; }
      }catch(e){}
    }));
    if(dirty){ if(S.trayScope==="all")loadHistory(); else renderTray(); }
    else for(const j of live){const el=document.querySelector('[data-elapsed="'+j.id+'"]'); if(el)el.textContent=Math.round(j.elapsed||0)+"s";}
  },1000);

  // ---------- event delegation ----------
  document.addEventListener("click",(e)=>{
    const t=e.target.closest("[data-act]"); if(!t)return;
    const a=t.dataset.act;
    if(a==="tool"){S.tool=t.dataset.tool;renderToolbar();redraw();}
    else if(a==="swatch"){S.color=t.dataset.color;S.tool="pen";renderToolbar();}
    else if(a==="brushDown"){S.brushLevel=Math.max(0,S.brushLevel-1);renderToolbar();}
    else if(a==="brushUp"){S.brushLevel=Math.min(4,S.brushLevel+1);renderToolbar();}
    else if(a==="undo"){if(S.strokes.length){S.strokes.pop();redraw();}}
    else if(a==="clear"){S.strokes=[];S.items=[];S.selectedId=null;renderToolbar();redraw();const h=$("hint");if(h)h.style.display="flex";}
    else if(a==="removeSel"){S.items=S.items.filter(it=>it.id!==S.selectedId);S.selectedId=null;renderToolbar();redraw();}
    else if(a==="zoomIn"){zoomAt(1.25);} else if(a==="zoomOut"){zoomAt(.8);}
    else if(a==="zoomReset"){S.view={x:0,y:0,s:1};updateZoom();redraw();} else if(a==="zoomFit"){zoomFit();}
    else if(a==="shortcuts"){S.shortcutsOpen=!S.shortcutsOpen;renderOverlays();}
    else if(a==="closeShortcuts"){S.shortcutsOpen=false;renderOverlays();}
    else if(a==="closeLightbox"){S.lightbox=null;renderOverlays();}
    else if(a==="togglePrompt"){S.promptExpanded=!S.promptExpanded;renderPrompt();}
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
  document.addEventListener("change",(e)=>{ if(e.target.dataset&&e.target.dataset.act==="custom"){S.customColor=e.target.value;S.color=e.target.value;S.tool="pen";renderToolbar();} });
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
    else if(k==="v"){S.tool="move";renderToolbar();redraw();} else if(k==="p"){S.tool="pen";renderToolbar();}
    else if(k==="e"){S.tool="eraser";renderToolbar();} else if(k==="d"){S.tool="strokeDel";renderToolbar();}
    else if(k==="["){S.brushLevel=Math.max(0,S.brushLevel-1);renderToolbar();} else if(k==="]"){S.brushLevel=Math.min(4,S.brushLevel+1);renderToolbar();}
    else if(k==="0"){S.view={x:0,y:0,s:1};updateZoom();redraw();} else if(k==="f"){zoomFit();}
  });
  window.addEventListener("resize",sizeCanvas);

  shell();
})();
</script></body></html>"""
