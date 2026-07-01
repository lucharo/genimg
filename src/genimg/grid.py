"""HTML grid renderer. Embeds images as base64; click image → clipboard.

Cost is not estimated here — the caller passes its authoritative figure (from cost.py)
via `cost_total`. This keeps a single source of truth for pricing.
"""
from __future__ import annotations

import base64
import webbrowser
from pathlib import Path


_HTML = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>genimg grid</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#1a1a1a;color:#fff;min-height:100vh;padding:20px}
  h1{text-align:center;margin-bottom:10px;font-weight:400;color:#888;font-size:14px}
  .toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#4CAF50;color:#fff;padding:12px 24px;border-radius:8px;opacity:0;transition:opacity .3s;z-index:1000;font-size:14px}
  .toast.show{opacity:1}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;max-width:1400px;margin:0 auto}
  .card{background:#2a2a2a;border-radius:12px;overflow:hidden;transition:transform .2s,box-shadow .2s;position:relative}
  .card:hover{transform:translateY(-4px);box-shadow:0 12px 24px rgba(0,0,0,.4)}
  .card img{width:100%;height:auto;display:block;cursor:pointer}
  .card .label{position:absolute;top:12px;left:12px;background:rgba(0,0,0,.5);color:#fff;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:500;pointer-events:none;z-index:2}
  .card .actions{padding:8px 12px;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .card .filename{font-size:12px;color:#888;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .card .btn{background:#333;border:1px solid #555;color:#ccc;padding:5px 12px;border-radius:4px;font-size:11px;cursor:pointer;transition:background .2s,color .2s;white-space:nowrap}
  .card .btn:hover{background:#4CAF50;color:#fff;border-color:#4CAF50}
  .instructions{text-align:center;margin-bottom:20px;color:#666;font-size:13px}
  .cost-footer{max-width:1400px;margin:24px auto 0;padding:16px 20px;background:#2a2a2a;border-radius:12px;display:flex;justify-content:space-between;align-items:center;font-size:13px}
  .cost-footer .total{color:#4CAF50;font-weight:600;font-size:15px}
  .cost-footer .detail{color:#888}
</style></head><body>
<h1>Click image to copy to clipboard | Click "Copy Text" for selection text</h1>
<p class="instructions">Paste directly into slides or back into the conversation</p>
<div id="toast" class="toast">Copied!</div>
<div class="grid">__CARDS__</div>
__COST_FOOTER__
<script>
  function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}
  function copyText(e,text,label){e.preventDefault();e.stopPropagation();
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(()=>showToast('Copied: '+label)).catch(()=>fallbackCopyText(text,label))
    } else {fallbackCopyText(text,label)} return false}
  function fallbackCopyText(text,label){const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);showToast('Copied: '+label)}
  async function copyImage(img,label){try{const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);const b=await new Promise(r=>c.toBlob(r,'image/png'));await navigator.clipboard.write([new ClipboardItem({'image/png':b})]);showToast('Image copied: '+label)}catch(err){showToast('Copy failed — try the button');console.error(err)}}
</script></body></html>'''

_CARD = '''
  <div class="card">
    <span class="label">{label}</span>
    <img src="{src}" alt="{label}" onclick="copyImage(this, '{label}')">
    <div class="actions">
      <span class="filename">{filename}</span>
      <button class="btn" onclick="copyImage(this.closest('.card').querySelector('img'), '{label}')">Copy Image</button>
      <button class="btn" onclick="copyText(event, '{copy_text}', '{label}')">Copy Text</button>
    </div>
  </div>'''


def _data_uri(path: Path) -> str:
  ext = path.suffix.lower()
  mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
  return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def render(images: list[Path], output: Path, *, embed: bool = True,
           copy_format: str = "I choose {label} ({filename})",
           cost_total: float | None = None) -> Path:
  """Render an HTML grid. Pass `cost_total` (the caller's authoritative estimate) to show a
  cost footer; omit it — as the standalone `grid` command does for arbitrary files whose
  provenance is unknown — and the footer is left out rather than showing a guessed number."""
  cards: list[str] = []
  for i, p in enumerate(images):
    label = f"#{i + 1}"
    src = _data_uri(p) if embed else str(p.absolute())
    text = copy_format.format(label=label, filename=p.name, path=str(p.absolute())).replace("'", "\\'")
    cards.append(_CARD.format(src=src, label=label, filename=p.name, copy_text=text))

  if cost_total is not None:
    footer = (
      f'<div class="cost-footer"><span class="detail">{len(images)} images</span>'
      f'<span class="total">Total: ${cost_total:.2f}</span></div>'
    )
  else:
    footer = ""
  html = _HTML.replace("__CARDS__", "".join(cards)).replace("__COST_FOOTER__", footer)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(html)
  return output


def open_in_browser(path: Path) -> None:
  webbrowser.open(f"file://{path.absolute()}")
