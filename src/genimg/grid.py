"""HTML grid renderer. Embeds images as base64; click image → clipboard.

Two views in one self-contained file: a responsive grid and a one-at-a-time
carousel, toggled client-side. Images are embedded once into a JS data array
and both views render from it, so the carousel adds no extra payload.
"""
from __future__ import annotations

import base64
import html
import json
import webbrowser
from pathlib import Path
from typing import Any

from PIL import Image

# Per-image cost map (rough). Google Imagen by max edge; OpenAI gpt-image-2 by quality+size.
_GOOGLE_COST_BY_EDGE = {1024: 0.04, 2048: 0.13, 4096: 0.24}
_OPENAI_COST_BY_QUALITY = {"low": 0.006, "medium": 0.053, "high": 0.211, "auto": 0.053}


def estimate_cost(img_path: Path, provider: str | None = None, quality: str | None = None) -> float:
  if provider == "openai":
    return _OPENAI_COST_BY_QUALITY.get(quality or "high", 0.053)
  try:
    with Image.open(img_path) as img:
      max_dim = max(img.size)
      for edge, cost in sorted(_GOOGLE_COST_BY_EDGE.items()):
        if max_dim <= edge:
          return cost
      return _GOOGLE_COST_BY_EDGE[4096]
  except Exception:
    return _GOOGLE_COST_BY_EDGE[1024]


_HTML = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>genimg grid</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#1a1a1a;color:#fff;min-height:100vh;padding:20px}
  h1{text-align:center;margin-bottom:10px;font-weight:400;color:#888;font-size:14px}
  .toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#4CAF50;color:#fff;padding:12px 24px;border-radius:8px;opacity:0;transition:opacity .3s;z-index:1000;font-size:14px}
  .toast.show{opacity:1}
  .meta{max-width:1400px;margin:0 auto 16px;background:#222;border:1px solid #333;border-radius:12px;padding:14px 18px;font-size:13px;color:#bbb}
  .meta .prompt{color:#e8e8e8;white-space:pre-wrap;word-break:break-word;margin-bottom:10px;line-height:1.45}
  .meta .fields{display:flex;flex-wrap:wrap;gap:8px 18px;color:#888}
  .meta .fields b{color:#ccc;font-weight:600}
  .viewbar{max-width:1400px;margin:0 auto 16px;display:flex;justify-content:center;gap:8px}
  .viewbar button{background:#2a2a2a;border:1px solid #444;color:#aaa;padding:7px 18px;border-radius:8px;font-size:13px;cursor:pointer;transition:background .2s,color .2s}
  .viewbar button.active{background:#4CAF50;color:#fff;border-color:#4CAF50}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;max-width:1400px;margin:0 auto}
  .card{background:#2a2a2a;border-radius:12px;overflow:hidden;transition:transform .2s,box-shadow .2s;position:relative}
  .card:hover{transform:translateY(-4px);box-shadow:0 12px 24px rgba(0,0,0,.4)}
  .card img{width:100%;height:auto;display:block;cursor:pointer}
  .card .label{position:absolute;top:12px;left:12px;background:rgba(0,0,0,.5);color:#fff;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:500;pointer-events:none;z-index:2}
  .card .actions{padding:8px 12px;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .card .filename{font-size:12px;color:#888;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .btn{background:#333;border:1px solid #555;color:#ccc;padding:5px 12px;border-radius:4px;font-size:11px;cursor:pointer;transition:background .2s,color .2s;white-space:nowrap}
  .btn:hover{background:#4CAF50;color:#fff;border-color:#4CAF50}
  .instructions{text-align:center;margin-bottom:20px;color:#666;font-size:13px}
  .cost-footer{max-width:1400px;margin:24px auto 0;padding:16px 20px;background:#2a2a2a;border-radius:12px;display:flex;justify-content:space-between;align-items:center;font-size:13px}
  .cost-footer .total{color:#4CAF50;font-weight:600;font-size:15px}
  .cost-footer .detail{color:#888}
  /* carousel */
  .carousel{display:none;max-width:1100px;margin:0 auto}
  .carousel.active{display:block}
  .grid.hidden{display:none}
  .stage{position:relative;background:#2a2a2a;border-radius:12px;overflow:hidden;display:flex;align-items:center;justify-content:center;min-height:300px}
  .stage img{max-width:100%;max-height:78vh;display:block;cursor:pointer}
  .stage .label{position:absolute;top:14px;left:14px;background:rgba(0,0,0,.55);color:#fff;padding:5px 12px;border-radius:6px;font-size:14px;font-weight:500;pointer-events:none}
  .nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.5);color:#fff;border:none;width:48px;height:48px;border-radius:50%;font-size:24px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s}
  .nav:hover{background:#4CAF50}
  .nav.prev{left:14px}
  .nav.next{right:14px}
  .car-bar{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 4px 0}
  .car-bar .counter{color:#aaa;font-size:13px}
  .car-bar .car-filename{color:#888;font-size:12px;flex:1;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style></head><body>
<h1>Click image to copy to clipboard | Click "Copy Text" for selection text</h1>
<p class="instructions">Paste directly into slides or back into the conversation</p>
<div id="toast" class="toast">Copied!</div>
__META__
<div class="viewbar">
  <button id="btn-grid" class="active" onclick="setView('grid')">Grid</button>
  <button id="btn-carousel" onclick="setView('carousel')">Carousel</button>
</div>
<div id="grid" class="grid"></div>
<div id="carousel" class="carousel">
  <div class="stage">
    <span class="label" id="car-label"></span>
    <button class="nav prev" onclick="step(-1)" aria-label="Previous">&#8249;</button>
    <img id="car-img" alt="" onclick="copyImage(this, IMAGES[curIdx].label)">
    <button class="nav next" onclick="step(1)" aria-label="Next">&#8250;</button>
  </div>
  <div class="car-bar">
    <span class="counter" id="car-counter"></span>
    <span class="car-filename" id="car-filename"></span>
    <span style="display:flex;gap:8px">
      <button class="btn" onclick="copyImage(document.getElementById('car-img'), IMAGES[curIdx].label)">Copy Image</button>
      <button class="btn" onclick="copyText(event, IMAGES[curIdx].copyText, IMAGES[curIdx].label)">Copy Text</button>
    </span>
  </div>
</div>
__COST_FOOTER__
<script>
  const IMAGES = __IMAGES__;
  let curIdx = 0;
  function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}
  function copyText(e,text,label){if(e){e.preventDefault();e.stopPropagation();}
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(()=>showToast('Copied: '+label)).catch(()=>fallbackCopyText(text,label))
    } else {fallbackCopyText(text,label)} return false}
  function fallbackCopyText(text,label){const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);showToast('Copied: '+label)}
  async function copyImage(img,label){try{const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);const b=await new Promise(r=>c.toBlob(r,'image/png'));await navigator.clipboard.write([new ClipboardItem({'image/png':b})]);showToast('Image copied: '+label)}catch(err){showToast('Copy failed — try the button');console.error(err)}}

  function buildGrid(){
    const g=document.getElementById('grid');
    g.innerHTML=IMAGES.map((im,i)=>`
      <div class="card">
        <span class="label">${im.label}</span>
        <img src="${im.src}" alt="${im.label}" onclick="copyImage(this, IMAGES[${i}].label)">
        <div class="actions">
          <span class="filename">${im.filename}</span>
          <button class="btn" onclick="copyImage(this.closest('.card').querySelector('img'), IMAGES[${i}].label)">Copy Image</button>
          <button class="btn" onclick="copyText(event, IMAGES[${i}].copyText, IMAGES[${i}].label)">Copy Text</button>
        </div>
      </div>`).join('');
  }
  function showCarousel(){
    const im=IMAGES[curIdx];
    document.getElementById('car-img').src=im.src;
    document.getElementById('car-label').textContent=im.label;
    document.getElementById('car-filename').textContent=im.filename;
    document.getElementById('car-counter').textContent=(curIdx+1)+' / '+IMAGES.length;
  }
  function step(d){curIdx=(curIdx+d+IMAGES.length)%IMAGES.length;showCarousel();}
  function setView(v){
    const grid=document.getElementById('grid'),car=document.getElementById('carousel');
    const isCar=v==='carousel';
    grid.classList.toggle('hidden',isCar);
    car.classList.toggle('active',isCar);
    document.getElementById('btn-grid').classList.toggle('active',!isCar);
    document.getElementById('btn-carousel').classList.toggle('active',isCar);
    if(isCar)showCarousel();
  }
  document.addEventListener('keydown',e=>{
    if(!document.getElementById('carousel').classList.contains('active'))return;
    if(e.key==='ArrowLeft')step(-1);else if(e.key==='ArrowRight')step(1);
  });
  buildGrid();
</script></body></html>'''


def _data_uri(path: Path) -> str:
  ext = path.suffix.lower()
  mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
  return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _js(value: Any) -> str:
  """JSON for safe inline embedding inside a <script> tag."""
  return (json.dumps(value)
          .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _meta_panel(meta: dict[str, Any] | None) -> str:
  """Render a generation-metadata header from the dict built by metadata.build()."""
  if not meta:
    return ""
  prompt = meta.get("prompt")
  model = " · ".join(str(v) for v in (meta.get("alias"), meta.get("model_id")) if v)
  fields: list[tuple[str, Any]] = [
    ("model", model or None),
    ("provider", meta.get("provider")),
    ("n", meta.get("n")),
    ("quality", meta.get("quality")),
    ("resolution", meta.get("resolution")),
    ("aspect", meta.get("aspect_ratio")),
    ("time", meta.get("time")),
  ]
  cost = meta.get("cost_usd_estimated")
  if cost is not None:
    fields.append(("est. cost", f"${cost:.2f}"))
  chips = "".join(
    f"<span><b>{html.escape(k)}:</b> {html.escape(str(v))}</span>"
    for k, v in fields if v is not None and v != ""
  )
  prompt_html = (
    f'<div class="prompt">{html.escape(str(prompt))}</div>' if prompt else ""
  )
  return f'<div class="meta">{prompt_html}<div class="fields">{chips}</div></div>'


def render(images: list[Path], output: Path, *, embed: bool = True,
           copy_format: str = "I choose {label} ({filename})",
           provider: str | None = None, quality: str | None = None,
           include_cost: bool = True, meta: dict[str, Any] | None = None) -> tuple[Path, float]:
  """Render an HTML grid + carousel. If `include_cost` is False (or provider
  unknown), the cost footer is omitted to avoid misleading totals. If `meta`
  (the dict from metadata.build) is given, a generation-metadata header is shown."""
  items: list[dict[str, str]] = []
  costs: list[float] = []
  for i, p in enumerate(images):
    label = f"#{i + 1}"
    src = _data_uri(p) if embed else str(p.absolute())
    text = copy_format.format(label=label, filename=p.name, path=str(p.absolute()))
    items.append({"src": src, "label": label, "filename": p.name, "copyText": text})
    costs.append(estimate_cost(p, provider=provider, quality=quality))

  total = sum(costs)
  if include_cost and provider is not None:
    detail = f"{len(images)} images x ${costs[0]:.2f}" if len(set(costs)) == 1 else f"{len(images)} images (mixed)"
    footer = f'<div class="cost-footer"><span class="detail">{detail}</span><span class="total">Total: ${total:.2f}</span></div>'
  else:
    footer = ""
  html_doc = (_HTML
              .replace("__META__", _meta_panel(meta))
              .replace("__COST_FOOTER__", footer)
              .replace("__IMAGES__", _js(items)))
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(html_doc)
  return output, total


def open_in_browser(path: Path) -> None:
  webbrowser.open(f"file://{path.absolute()}")
