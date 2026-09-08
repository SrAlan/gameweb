// ═══════════════════════════════════════════════════════════════
//  story-map.js — Visor de mapa de historia para Between Floors
//
//  Lee main.canvas desde la raíz del proyecto via fetch.
//  Para cambiar el archivo fuente, edita la constante CANVAS_FILE.
// ═══════════════════════════════════════════════════════════════

(function () {

const CANVAS_FILE = 'main.canvas'; // ruta relativa al index.html

// ─── STATE ───────────────────────────────────────────────────
let mapData = null;
let transform = { x: 0, y: 0, scale: 1 };
let dragging = false, lastMx = 0, lastMy = 0;
let selectedNode = null;
const nodeEls = new Map();
const edgeEls = new Map();

let wrap, scene, svg;

// ─── INIT ────────────────────────────────────────────────────
function init() {
  wrap  = document.getElementById('map-canvas-wrap');
  scene = document.getElementById('map-scene');
  svg   = document.getElementById('map-edges-svg');

  if (!wrap || !scene || !svg) {
    console.error('[story-map] Faltan elementos HTML del mapa.');
    return;
  }

  bindControls();
  loadCanvas();
}

// ─── FETCH DEL ARCHIVO .canvas ───────────────────────────────
function loadCanvas() {
  fetch(CANVAS_FILE)
    .then(res => {
      if (!res.ok) throw new Error(`No se pudo cargar ${CANVAS_FILE} (${res.status})`);
      return res.json();
    })
    .then(data => {
      if (!data.nodes) throw new Error('El archivo no tiene nodos válidos.');
      renderMap(data);
    })
    .catch(err => {
      console.error('[story-map]', err.message);
      // Mostrar error sutil dentro del área del mapa
      wrap.innerHTML += `<div style="
        position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
        font-family:'JetBrains Mono',monospace;font-size:12px;color:#6b6a88;gap:8px;
      ">⚠ No se encontró <strong style="color:#e0dff5">${CANVAS_FILE}</strong> — ponlo en la raíz del proyecto</div>`;
    });
}

// ─── MARKDOWN SIMPLE ─────────────────────────────────────────
function md(text) {
  let h = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^## (.+)$/gm,'<h2>$1</h2>')
    .replace(/^# (.+)$/gm,'<h1>$1</h1>')
    .replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/_(.+?)_/g,'<em>$1</em>')
    .replace(/^---$/gm,'<hr>')
    .replace(/^\|(.+)\|$/gm, row => {
      const cells = row.slice(1,-1).split('|').map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    })
    .replace(/^(\| *[-:]+ *)+\|?$/gm, '');
  h = h.replace(/(<tr>.*?<\/tr>\n?)+/gs, m => `<table>${m}</table>`);
  h = h.split('\n').map(line => {
    if (line.match(/^<(h[123]|table|hr|ul|ol|li|tr)/)) return line;
    if (line.trim() === '') return '';
    return `<p>${line}</p>`;
  }).join('');
  return h;
}

// ─── COLOR CLASS ─────────────────────────────────────────────
function colorClass(c) {
  return {'1':'mc-1','2':'mc-2','3':'mc-3','4':'mc-4','5':'mc-5','6':'mc-6'}[c] || '';
}

// ─── RENDER ──────────────────────────────────────────────────
function renderMap(data) {
  mapData = data;
  scene.innerHTML = '';
  scene.appendChild(svg);
  svg.querySelectorAll('path').forEach(p => p.remove());
  nodeEls.clear(); edgeEls.clear();

  const nodes   = data.nodes || [];
  const edges   = data.edges || [];
  const groups  = nodes.filter(n => n.type === 'group');
  const regular = nodes.filter(n => n.type !== 'group');

  groups.forEach(n  => renderNode(n, true));
  regular.forEach(n => renderNode(n, false));
  edges.forEach(e   => renderEdge(e, nodes));

  document.getElementById('mstat-nodes').textContent  = regular.length;
  document.getElementById('mstat-edges').textContent  = edges.length;
  document.getElementById('mstat-groups').textContent = groups.length;

  setTimeout(() => fitAll(nodes), 60);
  setTimeout(drawMinimap, 120);
}

function renderNode(n, isGroup) {
  const el = document.createElement('div');
  el.className = 'map-node' + (isGroup ? ' group-node' : '');

  const cc = colorClass(n.color);
  if (cc) el.classList.add(cc);
  else if (n.color && n.color.startsWith('#')) {
    el.style.borderColor = n.color + '80';
    el.style.background  = n.color + '10';
  }

  el.style.left   = n.x + 'px';
  el.style.top    = n.y + 'px';
  el.style.width  = n.width + 'px';
  el.style.height = n.height + 'px';
  el.style.zIndex = isGroup ? 1 : 5;

  if (isGroup) {
    const lbl = document.createElement('div');
    lbl.className   = 'map-node-label';
    lbl.textContent = n.label || '';
    el.appendChild(lbl);
  } else if (n.type === 'text' || !n.type) {
    const cnt = document.createElement('div');
    cnt.className = 'map-node-content';
    cnt.innerHTML = md(n.text || '');
    el.appendChild(cnt);
  } else if (n.type === 'file') {
    const cnt = document.createElement('div');
    cnt.className = 'map-node-content';
    cnt.innerHTML = `<span style="color:#6b6a88;font-size:10px">📄 ${n.file || 'archivo'}</span>`;
    el.appendChild(cnt);
  }

  el.addEventListener('click', e => { e.stopPropagation(); selectNode(n, el); });
  scene.appendChild(el);
  nodeEls.set(n.id, el);
}

function renderEdge(e, nodes) {
  const fn = nodes.find(n => n.id === e.fromNode);
  const tn = nodes.find(n => n.id === e.toNode);
  if (!fn || !tn) return;

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.classList.add('map-edge-path');
  path.setAttribute('marker-end', 'url(#marr)');
  setEdgePath(path, fn, tn, e.fromSide, e.toSide);
  svg.appendChild(path);
  edgeEls.set(e.id, path);
}

function sidePoint(n, side) {
  const cx = n.x + n.width / 2, cy = n.y + n.height / 2;
  if (side === 'top')    return { x: cx, y: n.y };
  if (side === 'bottom') return { x: cx, y: n.y + n.height };
  if (side === 'left')   return { x: n.x, y: cy };
  if (side === 'right')  return { x: n.x + n.width, y: cy };
  return { x: cx, y: cy };
}

function setEdgePath(path, fn, tn, fs, ts) {
  const from  = sidePoint(fn, fs || 'bottom');
  const to    = sidePoint(tn, ts || 'top');
  const dx = to.x - from.x, dy = to.y - from.y;
  const curve = Math.min(Math.sqrt(dx*dx + dy*dy) * 0.4, 120);
  let c1x=from.x, c1y=from.y, c2x=to.x, c2y=to.y;
  if ((fs||'bottom')==='bottom') c1y+=curve; else if (fs==='top') c1y-=curve;
  else if (fs==='right') c1x+=curve;         else if (fs==='left') c1x-=curve;
  if ((ts||'top')==='top') c2y-=curve;       else if (ts==='bottom') c2y+=curve;
  else if (ts==='left') c2x-=curve;          else if (ts==='right') c2x+=curve;
  path.setAttribute('d', `M${from.x},${from.y} C${c1x},${c1y} ${c2x},${c2y} ${to.x},${to.y}`);
}

// ─── SELECTION ───────────────────────────────────────────────
function selectNode(n, el) {
  if (selectedNode) {
    const prev = nodeEls.get(selectedNode.id);
    if (prev) prev.classList.remove('selected');
    edgeEls.forEach(p => { p.classList.remove('highlighted'); p.setAttribute('marker-end','url(#marr)'); });
  }
  if (selectedNode && selectedNode.id === n.id) {
    selectedNode = null;
    document.getElementById('map-detail').classList.remove('visible');
    return;
  }
  selectedNode = n;
  el.classList.add('selected');
  if (mapData) {
    mapData.edges.forEach(e => {
      if (e.fromNode === n.id || e.toNode === n.id) {
        const p = edgeEls.get(e.id);
        if (p) { p.classList.add('highlighted'); p.setAttribute('marker-end','url(#marr-hi)'); }
      }
    });
  }
  showDetail(n);
}

function showDetail(n) {
  const panel = document.getElementById('map-detail');
  const title = document.getElementById('map-detail-title');
  const body  = document.getElementById('map-detail-body');

  if (n.type === 'group') {
    title.textContent = 'Grupo';
    body.innerHTML = `<p style="color:#7c6af7;font-family:'Syne',sans-serif;font-weight:700">${n.label || '(sin nombre)'}</p>`;
  } else if (n.type === 'file') {
    title.textContent = 'Archivo';
    body.innerHTML = `<p>📄 <strong>${n.file || ''}</strong></p>`;
  } else {
    title.textContent = 'Nodo';
    body.innerHTML = md(n.text || '');
  }

  if (mapData) {
    const out = mapData.edges.filter(e => e.fromNode === n.id).length;
    const inc = mapData.edges.filter(e => e.toNode  === n.id).length;
    if (out || inc) {
      body.innerHTML += `<hr><p style="color:#6b6a88;font-size:10px;margin-top:4px">
        ↗ ${out} saliente${out !== 1 ? 's' : ''} &nbsp;
        ↙ ${inc} entrante${inc !== 1 ? 's' : ''}</p>`;
    }
  }
  panel.classList.add('visible');
}

// ─── CONTROLES ───────────────────────────────────────────────
function bindControls() {
  document.getElementById('map-detail-close').addEventListener('click', () => {
    document.getElementById('map-detail').classList.remove('visible');
    if (selectedNode) {
      const el = nodeEls.get(selectedNode.id);
      if (el) el.classList.remove('selected');
      edgeEls.forEach(p => { p.classList.remove('highlighted'); p.setAttribute('marker-end','url(#marr)'); });
      selectedNode = null;
    }
  });

  wrap.addEventListener('click', () => {
    if (selectedNode) {
      const el = nodeEls.get(selectedNode.id);
      if (el) el.classList.remove('selected');
      edgeEls.forEach(p => { p.classList.remove('highlighted'); p.setAttribute('marker-end','url(#marr)'); });
      selectedNode = null;
      document.getElementById('map-detail').classList.remove('visible');
    }
  });

  // Pan
  wrap.addEventListener('mousedown', e => {
    const t = e.target;
    if (t === wrap || t.id === 'map-grid-bg' || t.id === 'map-scene') {
      dragging = true;
      lastMx = e.clientX; lastMy = e.clientY;
      wrap.classList.add('panning');
    }
  });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    transform.x += e.clientX - lastMx;
    transform.y += e.clientY - lastMy;
    lastMx = e.clientX; lastMy = e.clientY;
    applyTransform();
  });
  window.addEventListener('mouseup', () => {
    dragging = false;
    wrap.classList.remove('panning');
  });

  // Zoom rueda
  wrap.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const ns = Math.max(0.05, Math.min(4, transform.scale * delta));
    transform.x = mx - (mx - transform.x) * (ns / transform.scale);
    transform.y = my - (my - transform.y) * (ns / transform.scale);
    transform.scale = ns;
    applyTransform();
  }, { passive: false });

  // Touch
  let touches = {};
  wrap.addEventListener('touchstart', e => {
    Array.from(e.changedTouches).forEach(t => touches[t.identifier] = { x: t.clientX, y: t.clientY });
  });
  wrap.addEventListener('touchmove', e => {
    e.preventDefault();
    if (e.touches.length === 1) {
      const t = e.touches[0];
      const prev = touches[t.identifier];
      if (prev) {
        transform.x += t.clientX - prev.x;
        transform.y += t.clientY - prev.y;
        applyTransform();
      }
      touches[t.identifier] = { x: t.clientX, y: t.clientY };
    }
  }, { passive: false });
  wrap.addEventListener('touchend', e => {
    Array.from(e.changedTouches).forEach(t => delete touches[t.identifier]);
  });

  // Botones
  document.getElementById('mbtn-fit').addEventListener('click',  () => { if (mapData) fitAll(mapData.nodes); });
  document.getElementById('mbtn-zin').addEventListener('click',  () => { transform.scale = Math.min(4, transform.scale * 1.2); applyTransform(); });
  document.getElementById('mbtn-zout').addEventListener('click', () => { transform.scale = Math.max(0.05, transform.scale * 0.8); applyTransform(); });

  // Pantalla completa
  const fsBtn = document.getElementById('mbtn-fullscreen');
  const mapSection = document.querySelector('.story-map-section');
  fsBtn.addEventListener('click', () => {
    const isFs = mapSection.classList.toggle('fullscreen');
    fsBtn.textContent = isFs ? '✕' : '⛶';
    fsBtn.title = isFs ? 'Salir de pantalla completa' : 'Pantalla completa';
    // Prevenir scroll del body en fullscreen
    document.body.style.overflow = isFs ? 'hidden' : '';
    setTimeout(() => { if (mapData) fitAll(mapData.nodes); }, 50);
  });
  // Salir con Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && mapSection.classList.contains('fullscreen')) {
      mapSection.classList.remove('fullscreen');
      fsBtn.textContent = '⛶';
      fsBtn.title = 'Pantalla completa';
      document.body.style.overflow = '';
    }
  });
}

// ─── TRANSFORM / FIT ─────────────────────────────────────────
function applyTransform() {
  scene.style.transform = `translate(${transform.x}px,${transform.y}px) scale(${transform.scale})`;
  drawMinimap();
}

function fitAll(nodes) {
  if (!nodes || !nodes.length) return;
  const W = wrap.offsetWidth, H = wrap.offsetHeight;
  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  nodes.forEach(n => {
    minX = Math.min(minX, n.x);          minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x+n.width);  maxY = Math.max(maxY, n.y+n.height);
  });
  const pw=maxX-minX, ph=maxY-minY, pad=60;
  const sc = Math.min((W-pad*2)/pw, (H-pad*2)/ph, 2);
  transform.scale = sc;
  transform.x = (W - pw*sc) / 2 - minX*sc;
  transform.y = (H - ph*sc) / 2 - minY*sc;
  applyTransform();
}

// ─── MINIMAP ─────────────────────────────────────────────────
function drawMinimap() {
  const cvs = document.getElementById('map-minimap-canvas');
  if (!mapData || !cvs) return;
  const W = cvs.offsetWidth * devicePixelRatio || 150;
  const H = cvs.offsetHeight * devicePixelRatio || 90;
  cvs.width = W; cvs.height = H;
  const ctx = cvs.getContext('2d');
  const nodes = mapData.nodes;
  if (!nodes.length) return;

  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  nodes.forEach(n => {
    minX=Math.min(minX,n.x); minY=Math.min(minY,n.y);
    maxX=Math.max(maxX,n.x+n.width); maxY=Math.max(maxY,n.y+n.height);
  });
  const pw=maxX-minX, ph=maxY-minY, pad=6;
  const sc = Math.min((W-pad*2)/pw, (H-pad*2)/ph);

  ctx.clearRect(0, 0, W, H);
  nodes.forEach(n => {
    const x=(n.x-minX)*sc+pad, y=(n.y-minY)*sc+pad;
    ctx.fillStyle   = n.type==='group' ? 'rgba(124,106,247,0.08)' : 'rgba(124,106,247,0.35)';
    ctx.strokeStyle = 'rgba(124,106,247,0.5)';
    ctx.lineWidth   = 0.5;
    ctx.fillRect(x, y, n.width*sc, n.height*sc);
    ctx.strokeRect(x, y, n.width*sc, n.height*sc);
  });

  const vx = (-transform.x/transform.scale - minX)*sc + pad;
  const vy = (-transform.y/transform.scale - minY)*sc + pad;
  const vW = (wrap.offsetWidth  / transform.scale) * sc;
  const vH = (wrap.offsetHeight / transform.scale) * sc;
  ctx.strokeStyle = 'rgba(247,106,200,0.8)';
  ctx.lineWidth   = 1.5;
  ctx.strokeRect(vx, vy, vW, vH);
}

// ─── ARRANCAR ────────────────────────────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

})();