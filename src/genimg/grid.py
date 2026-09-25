"""HTML grid renderer. Embeds images as base64; click image → clipboard.

Two views in one self-contained file: a responsive grid and a one-at-a-time
carousel, toggled client-side. Images are embedded once into a JS data array
and both views render from it, so the carousel adds no extra payload.

Layout: a collapsible prompt at the top (hidden by default), the view toggle,
the images, and a per-line metadata panel at the bottom with a single
harmonized cost estimate.
"""
from __future__ import annotations

import base64
import html
import json
import webbrowser
from pathlib import Path
from typing import Any

from PIL import Image

# Fallback per-image estimate for files of unknown provenance (`genimg grid *.png`), keyed by
# the image's long edge. Known generations carry `cost_usd_estimated` in their metadata.
_COST_BY_EDGE = {1024: 0.04, 2048: 0.13, 4096: 0.24}


def estimate_cost(img_path: Path, provider: str | None = None, quality: str | None = None,
                  model_id: str | None = None, resolution: str | None = None,
                  aspect: str | None = None) -> float:
  if provider and model_id:
    from .providers import get
    try:
      priced = get(provider).price(model_id, quality, resolution, aspect)
    except ValueError:
      priced = None
    if priced is not None:
      return priced
  try:
    with Image.open(img_path) as img:
      max_dim = max(img.size)
      for edge, cost in sorted(_COST_BY_EDGE.items()):
        if max_dim <= edge:
          return cost
      return _COST_BY_EDGE[4096]
  except Exception:
    return _COST_BY_EDGE[1024]


_HTML = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>genimg grid</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#1a1a1a;color:#fff;min-height:100vh;padding:20px}
  h1{text-align:center;margin-bottom:10px;font-weight:400;color:#888;font-size:14px}
  .toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#4CAF50;color:#fff;padding:12px 24px;border-radius:8px;opacity:0;transition:opacity .3s;z-index:1000;font-size:14px}
  .toast.show{opacity:1}
  .instructions{text-align:center;margin-bottom:16px;color:#666;font-size:13px}
  .promptbar{max-width:1400px;margin:0 auto 16px;text-align:left}
  .promptbox{max-width:1400px;margin:12px auto 0;background:#222;border:1px solid #333;border-radius:12px;padding:14px 18px;font-size:13px;line-height:1.5;color:#e8e8e8;white-space:pre-wrap;word-break:break-word;text-align:left}
  .promptbox[hidden]{display:none}
  .viewbar{max-width:1400px;margin:0 auto 16px;display:flex;justify-content:flex-start;gap:8px}
  .viewbar button{background:#2a2a2a;border:1px solid #444;color:#aaa;padding:7px 18px;border-radius:8px;font-size:13px;cursor:pointer;transition:background .2s,color .2s}
  .viewbar button.active{background:#4CAF50;color:#fff;border-color:#4CAF50}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;max-width:1400px;margin:0 auto}
  .card{background:#2a2a2a;border-radius:12px;overflow:hidden;transition:transform .2s,box-shadow .2s;position:relative}
  .card:hover{transform:translateY(-4px);box-shadow:0 12px 24px rgba(0,0,0,.4)}
  .card img{width:100%;height:auto;display:block;cursor:pointer}
  .card .label{position:absolute;top:12px;left:12px;background:rgba(0,0,0,.5);color:#fff;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:500;pointer-events:none;z-index:2}
  .card .delta{padding:8px 12px 0;font-size:12px;color:#8bc34a;font-style:italic}
  .card .actions{padding:8px 12px;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .card .filename{font-size:12px;color:#888;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .btn{background:#333;border:1px solid #555;color:#ccc;padding:6px 14px;border-radius:6px;font-size:12px;cursor:pointer;transition:background .2s,color .2s;white-space:nowrap}
  .btn:hover{background:#4CAF50;color:#fff;border-color:#4CAF50}
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
  .car-bar .car-delta{color:#8bc34a;font-size:12px;font-style:italic;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  /* metadata panel */
  .info{max-width:1400px;margin:24px auto 0;background:#2a2a2a;border-radius:12px;padding:8px 20px;font-size:13px}
  .info .row{display:flex;gap:16px;padding:8px 0;border-bottom:1px solid #333}
  .info .row:last-child{border-bottom:none}
  .info .k{color:#888;min-width:120px;flex-shrink:0}
  .info .v{color:#ddd;word-break:break-word}
  .info .row.cost .v{color:#4CAF50;font-weight:600}
  /* tournament: entry point */
  .viewbar{flex-wrap:wrap;align-items:center}
  .t-entry{margin-left:auto;display:flex;align-items:center;gap:6px;position:relative}
  .viewbar .t-open{border-color:#4CAF50;color:#cfe8d0}
  .t-info{width:26px;height:26px;border-radius:50%;background:#2a2a2a;border:1px solid #555;color:#aaa;font:600 13px/1 Georgia,serif;cursor:help}
  .t-tip{position:absolute;right:0;top:calc(100% + 8px);width:min(300px,calc(100vw - 40px));background:#2f2f2f;border:1px solid #444;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.45;color:#ddd;box-shadow:0 12px 28px rgba(0,0,0,.45);z-index:20;opacity:0;transform:translateY(-4px) scale(.97);transform-origin:top right;pointer-events:none;transition:opacity 150ms cubic-bezier(.23,1,.32,1),transform 150ms cubic-bezier(.23,1,.32,1)}
  .t-info:hover+.t-tip,.t-info:focus-visible+.t-tip,.t-info:focus+.t-tip{opacity:1;transform:none}
  .card .rank{position:absolute;top:12px;right:12px;background:#4CAF50;color:#fff;padding:4px 10px;border-radius:6px;font-size:12px;font-weight:600;pointer-events:none;z-index:2}
  .card .rank:empty{display:none}
  .btn:active,.viewbar button:active,.t-pick:active,.t-info:active{transform:scale(.97)}
  .btn,.viewbar button{transition:background .2s,color .2s,transform 160ms ease-out}
  .btn:disabled{opacity:.4;cursor:default;background:#333;color:#ccc;border-color:#555}
  /* tournament: dialog */
  body:has(dialog[open]){overflow:hidden}
  .tourney{position:fixed;inset:0;width:100%;height:100%;max-width:none;max-height:none;margin:0;border:0;padding:16px 20px 20px;background:#1a1a1a;color:#fff;overflow:auto}
  .tourney:focus{outline:none}
  .t-head{max-width:1400px;margin:0 auto 14px;display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
  .t-status{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;flex:1;min-width:0}
  .t-status strong{font-size:17px;font-weight:600}
  .t-status span{color:#999;font-size:13px}
  .t-tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
  .t-top3{display:flex;align-items:center;gap:6px;font-size:13px;color:#ccc;cursor:pointer;padding:0 4px}
  .t-top3 input{accent-color:#4CAF50;width:15px;height:15px}
  .t-top3 small{color:#888}
  .t-bar{flex-basis:100%;height:3px;background:#333;border-radius:2px;overflow:hidden}
  .t-bar i{display:block;height:100%;background:#4CAF50;transform-origin:left;transform:scaleX(0);transition:transform 200ms cubic-bezier(.23,1,.32,1)}
  .t-match{max-width:1400px;margin:0 auto;display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:16px;align-items:stretch}
  .t-match[hidden],.t-result[hidden]{display:none}
  .t-pick{background:#2a2a2a;border:2px solid #333;border-radius:12px;overflow:hidden;cursor:pointer;color:#ddd;display:flex;flex-direction:column;padding:0;text-align:left;font:inherit;transition:border-color .15s,transform 160ms ease-out}
  .t-pick:focus-visible{outline:2px solid #4CAF50;outline-offset:2px}
  .t-pick img{width:100%;height:calc(100vh - 210px);min-height:180px;object-fit:contain;background:#222;display:block}
  .t-cap{display:flex;align-items:center;gap:10px;padding:10px 12px;font-size:13px;min-width:0}
  .t-cap kbd{font:600 12px/1 -apple-system,BlinkMacSystemFont,sans-serif;background:#1a1a1a;border:1px solid #555;border-bottom-width:2px;border-radius:5px;padding:4px 7px;color:#ccc}
  .t-cap .t-name{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .t-cap .t-model{color:#8bc34a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:45%}
  .t-vs{align-self:center;color:#666;font-size:13px;letter-spacing:.08em;text-transform:uppercase}
  .t-hint{max-width:1400px;margin:12px auto 0;color:#666;font-size:12px;text-align:center}
  @media (hover:hover) and (pointer:fine){.t-pick:hover{border-color:#4CAF50}}
  @media (hover:none){.t-cap kbd{display:none}}
  .t-result{max-width:1100px;margin:0 auto}
  .t-podium{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) minmax(0,1fr);gap:16px;align-items:start}
  .t-place{background:#2a2a2a;border-radius:12px;overflow:hidden;margin:0}
  .t-place img{width:100%;aspect-ratio:1;object-fit:contain;background:#222;display:block}
  .t-place figcaption{padding:10px 12px;font-size:13px;color:#ddd;display:flex;flex-direction:column;gap:3px;min-width:0}
  .t-place figcaption span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .t-place .t-model{color:#8bc34a;font-size:12px}
  .t-medal{font-size:12px;font-weight:600;letter-spacing:.04em;color:#888;text-transform:uppercase}
  .t-place.p1 .t-medal{color:#4CAF50}
  .t-third{background:none;border:1px dashed #555;border-radius:12px;color:#aaa;min-height:160px;font:inherit;font-size:14px;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;align-self:stretch;transition:border-color .15s,color .15s,transform 160ms ease-out}
  .t-third small{color:#777;font-size:12px}
  .t-third:hover{border-color:#4CAF50;color:#fff}
  .t-third:active{transform:scale(.98)}
  .t-actions{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
  .t-actions .primary{background:#4CAF50;border-color:#4CAF50;color:#fff}
  .t-history{background:#222;border:1px solid #333;border-radius:12px;padding:10px 16px;font-size:13px;color:#bbb}
  .t-history summary{cursor:pointer;color:#ccc}
  .t-history ol{margin:10px 0 4px 20px;line-height:1.7}
  .t-history b{color:#fff;font-weight:600}
  @media (max-width:640px){
    body{padding:14px}
    .tourney{padding:12px 14px 16px}
    .t-match{grid-template-columns:minmax(0,1fr);gap:8px}
    .t-pick img{height:calc(50vh - 150px);min-height:120px}
    .t-vs{display:none}
    .t-podium{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
    .t-podium .p1{grid-column:1 / -1}
  }
  @media (prefers-reduced-motion:reduce){.t-tip,.t-bar i{transition:opacity 150ms}.t-tip{transform:none}}
</style></head><body>
<h1>Click image to copy to clipboard | Click "Copy Text" for selection text</h1>
<p class="instructions">Paste directly into slides or back into the conversation</p>
__PROMPT_TOP__
<div class="viewbar">
  <button id="btn-grid" class="active" onclick="setView('grid')">Grid</button>
  <button id="btn-carousel" onclick="setView('carousel')">Carousel</button>
__TOURNEY_ENTRY__
</div>
<div id="toast" class="toast">Copied!</div>
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
    <span class="car-delta" id="car-delta"></span>
    <span class="car-filename" id="car-filename"></span>
    <span style="display:flex;gap:8px">
      <button class="btn" onclick="copyImage(document.getElementById('car-img'), IMAGES[curIdx].label)">Copy Image</button>
      <button class="btn" onclick="copyText(event, IMAGES[curIdx].copyText, IMAGES[curIdx].label)">Copy Text</button>
    </span>
  </div>
</div>
__INFO_PANEL__
__TOURNEY_DIALOG__
<script>
  const IMAGES = __IMAGES__;
  const GENERATION_ID = __GENERATION_ID__;
  const SECS_PER_PICK = __SECS_PER_PICK__;
  let curIdx = 0;
  // Tournament state: seeding (image indices), one winner index per match played, top-3 flag.
  // Declared up here because writeUrl() and restore() read it.
  const TOUR = {order: null, picks: [], top3: false};
  const TOUR_DLG = document.getElementById('tourney');
  // --- URL state: view (grid|carousel), prompt (0|1), i (1-based carousel index),
  // tournament t (seeding) / tp (picks) as dot-joined 1-based positions, t3 (top 3), tv (open) ---
  function writeUrl(){
    const p=new URLSearchParams();
    const isCar=document.getElementById('carousel').classList.contains('active');
    if(isCar){p.set('view','carousel');p.set('i',String(curIdx+1));}
    const pb=document.getElementById('promptbox');
    if(pb&&!pb.hasAttribute('hidden'))p.set('prompt','1');
    if(TOUR.order){
      p.set('t',TOUR.order.map(i=>i+1).join('.'));
      if(TOUR.picks.length)p.set('tp',TOUR.picks.map(i=>i+1).join('.'));
      if(TOUR.top3)p.set('t3','1');
      if(TOUR_DLG&&TOUR_DLG.open)p.set('tv','1');
    }
    const qs=p.toString();
    history.replaceState(null,'',qs?('?'+qs):location.pathname);
  }
  function readUrl(){return new URLSearchParams(location.search);}
  function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}
  function setPrompt(show){const b=document.getElementById('promptbox'),btn=document.getElementById('prompt-toggle');if(!b)return;if(show){b.removeAttribute('hidden');btn.textContent='Hide prompt';}else{b.setAttribute('hidden','');btn.textContent='Show prompt';}}
  function togglePrompt(){const b=document.getElementById('promptbox');if(!b)return;setPrompt(b.hasAttribute('hidden'));writeUrl();}
  function copyText(e,text,label){if(e){e.preventDefault();e.stopPropagation();}
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(()=>showToast('Copied: '+label)).catch(()=>fallbackCopyText(text,label))
    } else {fallbackCopyText(text,label)} return false}
  function fallbackCopyText(text,label){const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);showToast('Copied: '+label)}
  async function copyImage(img,label){try{const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;c.getContext('2d').drawImage(img,0,0);const b=await new Promise(r=>c.toBlob(r,'image/png'));await navigator.clipboard.write([new ClipboardItem({'image/png':b})]);showToast('Image copied: '+label)}catch(err){showToast('Copy failed — try the button');console.error(err)}}

  function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
  function buildGrid(){
    const g=document.getElementById('grid');
    g.innerHTML=IMAGES.map((im,i)=>`
      <div class="card">
        <span class="label">${esc(im.label)}</span>
        <span class="rank"></span>
        <img src="${esc(im.src)}" alt="${esc(im.label)}" onclick="copyImage(this, IMAGES[${i}].label)">
        ${im.delta?`<div class="delta">${esc(im.delta)}</div>`:''}
        <div class="actions">
          <span class="filename">${esc(im.filename)}</span>
          <button class="btn" onclick="copyImage(this.closest('.card').querySelector('img'), IMAGES[${i}].label)">Copy Image</button>
          <button class="btn" onclick="copyText(event, IMAGES[${i}].copyText, IMAGES[${i}].label)">Copy Text</button>
        </div>
      </div>`).join('');
  }
  function showCarousel(){
    const im=IMAGES[curIdx];
    document.getElementById('car-img').src=im.src;
    document.getElementById('car-label').textContent=im.label;
    document.getElementById('car-delta').textContent=im.delta||'';
    document.getElementById('car-filename').textContent=im.filename;
    document.getElementById('car-counter').textContent=(curIdx+1)+' / '+IMAGES.length;
  }
  function step(d){curIdx=(curIdx+d+IMAGES.length)%IMAGES.length;showCarousel();writeUrl();}
  function setView(v){
    const grid=document.getElementById('grid'),car=document.getElementById('carousel');
    const isCar=v==='carousel';
    grid.classList.toggle('hidden',isCar);
    car.classList.toggle('active',isCar);
    document.getElementById('btn-grid').classList.toggle('active',!isCar);
    document.getElementById('btn-carousel').classList.toggle('active',isCar);
    if(isCar)showCarousel();
    writeUrl();
  }
  document.addEventListener('keydown',e=>{
    if(TOUR_DLG&&TOUR_DLG.open){
      if(e.key==='ArrowLeft'){e.preventDefault();pick('a');}
      else if(e.key==='ArrowRight'){e.preventDefault();pick('b');}
      else if(e.key==='Backspace'){e.preventDefault();undoPick();}
      return;
    }
    if(!document.getElementById('carousel').classList.contains('active'))return;
    if(e.key==='ArrowLeft')step(-1);else if(e.key==='ArrowRight')step(1);
  });

  // <tourney-core> Pure bracket logic, no DOM; tests run this block under node.
  // Single elimination. order: seeding (any ids). picks: the winner of each match, in play
  // order. Byes go to the first seeds so no first-round slot is bye-vs-bye, which keeps every
  // later match real: a winner costs exactly n-1 picks. With top3 and two real semifinals, the
  // semifinal losers play one more match after the final; with n=3 third place is free.
  function roundName(slots){return slots===2?'Final':slots===4?'Semifinal':slots===8?'Quarterfinal':'Round of '+slots}
  function bracket(order,picks,top3){
    const n=order.length;let size=1;while(size<n)size*=2;
    const byes=size-n;let pairs=[],k=0;
    for(let i=0;i<size/2;i++){if(i<byes){pairs.push([order[k],null]);k+=1;}else{pairs.push([order[k],order[k+1]]);k+=2;}}
    const played=[];let used=0,current=null,slots=size,champion=null;
    function play(a,b,round){
      if(current)return null;
      const p=picks[used];
      if(p!==a&&p!==b){current={a,b,round};return null;}
      used++;played.push({a,b,winner:p,loser:p===a?b:a,round});return p;
    }
    for(;;){
      const winners=pairs.map(([a,b])=>b===null?a:play(a,b,roundName(slots)));
      if(current)break;
      if(winners.length===1){champion=winners[0];break;}
      pairs=[];for(let i=0;i<winners.length;i+=2)pairs.push([winners[i],winners[i+1]]);
      slots/=2;
    }
    const ranking=[];
    if(champion!==null){
      ranking.push(champion,played[played.length-1].loser);
      const semiLosers=played.filter(m=>m.round==='Semifinal').map(m=>m.loser);
      if(semiLosers.length===1)ranking.push(semiLosers[0]);
      else if(top3){const w=play(semiLosers[0],semiLosers[1],'Third place');if(w!==null)ranking.push(w);}
    }
    return {played,current,ranking,used,done:champion!==null&&current===null,total:n-1+(top3&&n>=4?1:0)};
  }
  // </tourney-core>

  function shuffled(n){const a=[...Array(n).keys()];for(let i=n-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a}
  function tourState(){const s=bracket(TOUR.order,TOUR.picks,TOUR.top3);TOUR.picks.length=s.used;return s}
  function eta(picksLeft){const s=picksLeft*SECS_PER_PICK;return s<60?'~'+Math.max(5,Math.round(s/5)*5)+' s left':'~'+Math.round(s/60)+' min left'}
  function ordinal(r){return ['1st','2nd','3rd'][r]}
  function entry(i){const im=IMAGES[i],o={id:im.label,position:i+1,filename:im.filename};if(im.model)o.model=im.model;if(im.provider)o.provider=im.provider;return o}
  function tourneyResult(){
    const s=tourState(),out={kind:'genimg-tournament',complete:s.done,images:IMAGES.length,top3:TOUR.top3,
      winner:s.done?entry(s.ranking[0]):null,
      ranking:s.done?s.ranking.map((i,r)=>Object.assign({rank:r+1},entry(i))):[],
      seeding:TOUR.order.map(i=>IMAGES[i].label),
      choices:s.played.map((m,k)=>({match:k+1,round:m.round,a:IMAGES[m.a].label,b:IMAGES[m.b].label,winner:IMAGES[m.winner].label}))};
    if(GENERATION_ID)out.generation_id=GENERATION_ID;
    return out;
  }
  function markRanks(s){
    const cards=document.querySelectorAll('#grid .card .rank');
    cards.forEach(c=>{c.textContent='';});
    if(s&&s.done)s.ranking.forEach((i,r)=>{if(cards[i])cards[i].textContent=ordinal(r);});
  }
  function setPick(side,i){
    const b=document.getElementById('t-'+side),im=IMAGES[i];
    b.querySelector('img').src=im.src;
    b.querySelector('.t-name').textContent=im.label+' · '+im.filename;
    b.querySelector('.t-model').textContent=im.model||'';
    b.setAttribute('aria-label','Pick '+im.label+' '+im.filename);
  }
  function placeHtml(i,r){
    const im=IMAGES[i];
    return `<figure class="t-place p${r+1}"><img src="${esc(im.src)}" alt="${esc(im.label)}">
      <figcaption><span class="t-medal">${ordinal(r)}${r===0?' · winner':''}</span>
      <span>${esc(im.label)} · ${esc(im.filename)}</span>${im.model?`<span class="t-model">${esc(im.model)}</span>`:''}</figcaption></figure>`;
  }
  function renderTourney(){
    const s=tourState(),done=s.played.length;
    document.getElementById('t-top3').checked=TOUR.top3;
    document.getElementById('t-undo').disabled=done===0;
    document.getElementById('t-fill').style.transform='scaleX('+(done/s.total)+')';
    const match=document.getElementById('t-match'),result=document.getElementById('t-result');
    if(s.current){
      document.getElementById('t-count').textContent='Match '+(done+1)+' of '+s.total;
      document.getElementById('t-round').textContent=s.current.round;
      document.getElementById('t-eta').textContent=eta(s.total-done);
      setPick('a',s.current.a);setPick('b',s.current.b);
      match.hidden=false;result.hidden=true;
    }else{
      document.getElementById('t-count').textContent=s.ranking.length===3?'Your top 3':'Your winner';
      document.getElementById('t-round').textContent=done+' picks';
      document.getElementById('t-eta').textContent='';
      const third=s.ranking.length===2?'<button class="t-third" onclick="setTop3(true)">Find 3rd place<small>1 more match</small></button>':'';
      document.getElementById('t-podium').innerHTML=s.ranking.map(placeHtml).join('')+third;
      document.getElementById('t-log').innerHTML=s.played.map(m=>`<li>${esc(m.round)}: <b>${esc(IMAGES[m.winner].label)}</b> over ${esc(IMAGES[m.loser].label)}</li>`).join('');
      document.getElementById('t-log-n').textContent=done;
      match.hidden=true;result.hidden=false;
    }
    markRanks(s);
  }
  function openTourney(){
    if(!TOUR.order)TOUR.order=shuffled(IMAGES.length);
    renderTourney();
    if(!TOUR_DLG.open){TOUR_DLG.showModal();TOUR_DLG.focus();}
    writeUrl();
  }
  function closeTourney(){TOUR_DLG.close()}
  function pick(side){const s=tourState();if(!s.current)return;TOUR.picks.push(side==='a'?s.current.a:s.current.b);renderTourney();writeUrl()}
  function undoPick(){if(!TOUR.picks.length)return;TOUR.picks.pop();renderTourney();writeUrl()}
  function reshuffle(){TOUR.order=shuffled(IMAGES.length);TOUR.picks=[];renderTourney();writeUrl()}
  function setTop3(on){TOUR.top3=on;renderTourney();writeUrl()}
  function copyFromDialog(btn,text){
    const done=()=>{const t=btn.textContent;btn.textContent='Copied';setTimeout(()=>{btn.textContent=t},1500)};
    const fallback=()=>{const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.left='-9999px';TOUR_DLG.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();done()};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(text).then(done).catch(fallback);else fallback();
  }
  function copyResultJson(btn){copyFromDialog(btn,JSON.stringify(tourneyResult(),null,2))}
  function copyWinnerText(btn){const s=tourState();if(s.done)copyFromDialog(btn,IMAGES[s.ranking[0]].copyText)}
  function parsePositions(v){
    if(!v)return [];
    const a=v.split('.').map(x=>parseInt(x,10)-1);
    return a.every(i=>Number.isInteger(i)&&i>=0&&i<IMAGES.length)?a:null;
  }
  function restoreTourney(q){
    if(!TOUR_DLG)return;
    TOUR_DLG.addEventListener('close',()=>{writeUrl();document.getElementById('btn-tourney').focus();});
    const order=parsePositions(q.get('t'));
    if(!order||order.length!==IMAGES.length||new Set(order).size!==order.length)return;
    TOUR.order=order;TOUR.picks=parsePositions(q.get('tp'))||[];TOUR.top3=q.get('t3')==='1';
    markRanks(tourState());
    if(q.get('tv')==='1')openTourney();
  }
  function restore(){
    const q=readUrl();
    if(q.get('prompt')==='1')setPrompt(true);
    const n=parseInt(q.get('i'),10);
    if(Number.isFinite(n)&&n>=1&&n<=IMAGES.length)curIdx=n-1;
    restoreTourney(q);
    if(q.get('view')==='carousel')setView('carousel');else writeUrl();
  }
  buildGrid();
  restore();
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


def _prompt_top(meta: dict[str, Any] | None) -> str:
  """Collapsible prompt block, hidden by default, with a Show prompt toggle."""
  prompt = (meta or {}).get("prompt")
  if not prompt:
    return ""
  return (
    '<div class="promptbar">'
    '<button id="prompt-toggle" class="btn" onclick="togglePrompt()">Show prompt</button>'
    f'<div id="promptbox" class="promptbox" hidden>{html.escape(str(prompt))}</div>'
    '</div>'
  )


# Tournament bounds: a pairwise bracket earns its keep from 3 images (issue #22); past 20 the
# page shows no entry point, since the grid has no selection to narrow the field with.
TOURNEY_MIN, TOURNEY_MAX = 3, 20
# Issue #22's estimate: eight images, seven picks, about a minute.
_SECS_PER_PICK = 8


def _tourney_eta(n: int) -> str:
  minutes = max(1, round((n - 1) * _SECS_PER_PICK / 60))
  return f"about {minutes} min"


def _tourney_entry(n: int) -> str:
  """Viewbar button plus a hover/focus explainer; empty outside the tournament bounds."""
  if not TOURNEY_MIN <= n <= TOURNEY_MAX:
    return ""
  return (
    '<span class="t-entry">'
    '<button id="btn-tourney" class="t-open" onclick="openTourney()">Tournament</button>'
    '<button type="button" class="t-info" aria-label="What is the tournament?" aria-describedby="t-tip">i</button>'
    '<span role="tooltip" id="t-tip" class="t-tip">Many images and can\'t decide? Compare them two at a time '
    f'until you have your winner, or your top 3. {n} images take {n - 1} picks, {_tourney_eta(n)}.</span>'
    '</span>'
  )


def _tourney_dialog(n: int) -> str:
  if not TOURNEY_MIN <= n <= TOURNEY_MAX:
    return ""
  third_cost = "+1 match" if n >= 4 else "no extra match"
  return f'''<dialog id="tourney" class="tourney" aria-labelledby="t-count" tabindex="-1">
  <header class="t-head">
    <div class="t-status"><strong id="t-count"></strong><span id="t-round"></span><span id="t-eta"></span></div>
    <div class="t-tools">
      <label class="t-top3"><input type="checkbox" id="t-top3" onchange="setTop3(this.checked)"> Top 3 <small>{third_cost}</small></label>
      <button class="btn" id="t-undo" onclick="undoPick()">Undo</button>
      <button class="btn" onclick="reshuffle()">Reshuffle</button>
      <button class="btn" onclick="closeTourney()">Close</button>
    </div>
    <div class="t-bar"><i id="t-fill"></i></div>
  </header>
  <div class="t-match" id="t-match">
    <button class="t-pick" id="t-a" onclick="pick('a')" aria-keyshortcuts="ArrowLeft"><img alt="">
      <span class="t-cap"><kbd>&larr;</kbd><span class="t-name"></span><span class="t-model"></span></span></button>
    <span class="t-vs">vs</span>
    <button class="t-pick" id="t-b" onclick="pick('b')" aria-keyshortcuts="ArrowRight"><img alt="">
      <span class="t-cap"><kbd>&rarr;</kbd><span class="t-name"></span><span class="t-model"></span></span></button>
  </div>
  <div class="t-result" id="t-result" hidden>
    <div class="t-podium" id="t-podium"></div>
    <div class="t-actions">
      <button class="btn primary" onclick="copyResultJson(this)">Copy result (JSON)</button>
      <button class="btn" onclick="copyWinnerText(this)">Copy Text</button>
      <button class="btn" onclick="reshuffle()">Run again</button>
      <button class="btn" onclick="closeTourney()">Back to grid</button>
    </div>
    <details class="t-history"><summary>How it went: <span id="t-log-n"></span> picks</summary><ol id="t-log"></ol></details>
  </div>
  <p class="t-hint">Click an image or press &larr; / &rarr;. Backspace undoes. Esc closes and keeps your place.</p>
</dialog>'''


def _diverse_note(meta: dict[str, Any]) -> str | None:
  """Info-panel value for the diverse row: names WHICH mechanism produced the spread."""
  if not meta.get("diverse"):
    return None
  has_deltas = any(isinstance(o, dict) and "prompt_delta" in o for o in meta.get("outputs", []))
  return "yes (per-card prompt deltas)" if has_deltas else "yes (model-diversified in one batched request)"


def _info_panel(meta: dict[str, Any] | None, cost: float | None) -> str:
  """Bottom metadata panel: one field per line, single harmonized cost."""
  from . import cost as pricing
  from . import provenance

  meta = meta or {}
  model = " · ".join(str(v) for v in (meta.get("alias"), meta.get("model_id")) if v)
  rows: list[tuple[str, Any, bool]] = [
    ("model", model or None, False),
    ("provider", meta.get("provider"), False),
    ("billing", pricing.billing_label(meta) if meta else None, False),
    ("reported generator", provenance.describe(meta["outputs"]) + " (C2PA, unverified)" if "api_equivalent_cost" in meta else None, False),
    ("API equivalent", pricing.format_equivalent(meta["api_equivalent_cost"]) + " (theoretical, rough, output only)" if "api_equivalent_cost" in meta else None, False),
    ("edit input", Path(meta["input"]).name if meta.get("input") else None, False),
  ]
  rows.extend(
    (f"reference {i}", Path(ref).name, False)
    for i, ref in enumerate(meta.get("refs") or [], start=1)
  )
  rows.extend([
    ("n", meta.get("n"), False),
    ("mode", meta.get("mode"), False),
    ("diverse", _diverse_note(meta), False),
    ("quality", meta.get("quality"), False),
    ("resolution", meta.get("resolution"), False),
    ("aspect ratio", meta.get("aspect_ratio"), False),
    ("time", meta.get("time"), False),
  ])
  if cost is not None:
    rows.append(("est. cost", f"${cost:.2f}", True))
  html_rows = "".join(
    f'<div class="row{" cost" if is_cost else ""}">'
    f'<span class="k">{html.escape(k)}</span>'
    f'<span class="v">{html.escape(str(v))}</span></div>'
    for k, v, is_cost in rows if v is not None and v != ""
  )
  return f'<div class="info">{html_rows}</div>' if html_rows else ""


def render(images: list[Path], output: Path, *, embed: bool = True,
           copy_format: str = "I choose {label} ({filename})",
           provider: str | None = None, quality: str | None = None,
           include_cost: bool = True, meta: dict[str, Any] | None = None) -> tuple[Path, float | None]:
  """Render an HTML grid + carousel with a collapsible prompt and a bottom
  metadata panel. The cost shown is a single harmonized estimate: the value
  from `meta` (`cost_usd_estimated`, which the CLI computes with full size/quality
  context) when available, else the renderer's own per-image estimate. If
  `include_cost` is False (or provider unknown and no meta cost), no cost is shown."""
  # Diverse mode (-d): each card shows the prompt delta that produced it.
  deltas_by_name: dict[str, str] = {}
  if meta and meta.get("diverse"):
    for out in meta.get("outputs", []):
      if isinstance(out, dict) and out.get("path"):
        deltas_by_name[Path(out["path"]).name] = out.get("prompt_delta") or "base prompt"

  # Which model made each card: the generation's own meta for `-g`, else each file's sidecar,
  # so a mixed-provider `genimg grid a.png b.png` still names its models.
  from . import metadata
  index = {} if meta else metadata.outputs_index()

  items: list[dict[str, str | None]] = []
  costs: list[float] = []
  for i, p in enumerate(images):
    label = f"#{i + 1}"
    src = _data_uri(p) if embed else str(p.absolute())
    text = copy_format.format(label=label, filename=p.name, path=str(p.absolute()))
    made_by = ({"model": meta.get("alias") or meta.get("model_id"), "provider": meta.get("provider")}
               if meta else index.get(str(p.resolve()), {}))
    items.append({"src": src, "label": label, "filename": p.name, "copyText": text,
                  "delta": deltas_by_name.get(p.name, ""),
                  "model": made_by.get("model"), "provider": made_by.get("provider")})
    costs.append(estimate_cost(p, provider=provider, quality=quality,
                               model_id=(meta or {}).get("model_id"), resolution=(meta or {}).get("resolution"),
                               aspect=(meta or {}).get("aspect_ratio")))

  # Single source of truth for cost: prefer the CLI's size/quality-aware estimate.
  meta_cost = (meta or {}).get("cost_usd_estimated")
  if meta_cost is not None:
    cost: float | None = float(meta_cost)
  elif meta is not None and "cost_usd_estimated" in meta:
    cost = None  # Explicitly unpriced; do not substitute another model's estimate.
  elif include_cost and provider is not None:
    cost = sum(costs)
  else:
    cost = None

  html_doc = (_HTML
              .replace("__PROMPT_TOP__", _prompt_top(meta))
              .replace("__INFO_PANEL__", _info_panel(meta, cost))
              .replace("__TOURNEY_ENTRY__", _tourney_entry(len(images)))
              .replace("__TOURNEY_DIALOG__", _tourney_dialog(len(images)))
              .replace("__GENERATION_ID__", _js((meta or {}).get("id")))
              .replace("__SECS_PER_PICK__", str(_SECS_PER_PICK))
              .replace("__IMAGES__", _js(items)))
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(html_doc)
  return output, cost


def open_in_browser(path: Path) -> None:
  webbrowser.open(path.absolute().as_uri())
