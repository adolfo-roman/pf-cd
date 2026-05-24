// inbox.js — panel estilo Google Messages con análisis automático + Gmail real

const SIGNAL_ICONS = { keywords:'🔤', uppercase:'🔠', phone:'📞', url:'🔗', money:'💰', exclamation:'❗' };

const AV_COLORS = ['av-blue','av-red','av-green','av-purple','av-orange','av-teal','av-pink'];
function avatarColor(name) {
  let h = 0;
  for (const c of (name || 'X')) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
  return AV_COLORS[Math.abs(h) % AV_COLORS.length];
}
function avatarLetter(name) { return (name || '?')[0].toUpperCase(); }

let allMessages   = [];
let selectedId    = null;
let currentSource = 'db';   // 'db' | 'gmail'
let gmailConnected    = false;
let gmailHasCreds     = false;

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Leer parámetros de URL (retorno de OAuth)
  const params = new URLSearchParams(window.location.search);
  if (params.get('gmail_ok'))    showToast('✅ Gmail conectado correctamente', 'ok');
  if (params.get('gmail_error')) showToast('❌ Error al conectar Gmail', 'err');
  if (params.get('gmail_ok') || params.get('gmail_error')) {
    history.replaceState({}, '', window.location.pathname);
  }

  await checkDbStatus();
  await checkGmailStatus();
  await loadMessages();

  document.getElementById('inbox-search').addEventListener('input', e => {
    renderList(e.target.value.toLowerCase());
  });
});

// ── DB Status ──────────────────────────────────────────────────────────────
async function checkDbStatus() {
  const bar = document.getElementById('db-status-bar');
  try {
    const res  = await fetch('/api/db-status');
    const data = await res.json();
    bar.style.display = 'flex';
    if (data.ok) {
      bar.className = 'db-bar-ok';
      bar.style.cssText += ';padding:.5rem 1rem;border-radius:.5rem;font-size:.8125rem;font-family:monospace;display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem';
      bar.innerHTML = `✅ BD conectada — ${data.host} · ${data.db} · ${data.latency_ms}ms`;
    } else {
      bar.className = 'db-bar-warn';
      bar.style.cssText += ';padding:.5rem 1rem;border-radius:.5rem;font-size:.8125rem;font-family:monospace;display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem';
      bar.innerHTML = `⚠️ BD no configurada — mostrando datos demo.`;
    }
  } catch { bar.style.display = 'none'; }
}

// ── Gmail Status ───────────────────────────────────────────────────────────
async function checkGmailStatus() {
  try {
    const res  = await fetch('/api/gmail/status');
    const data = await res.json();
    gmailConnected  = data.connected  || false;
    gmailHasCreds   = data.has_credentials || false;
  } catch {
    gmailConnected = false;
    gmailHasCreds  = false;
  }
  renderGmailBar();
}

function renderGmailBar() {
  const bar = document.getElementById('gmail-bar');
  if (!bar) return;

  if (gmailConnected) {
    bar.style.display = 'flex';
    bar.innerHTML = `
      <span style="display:flex;align-items:center;gap:.4rem">
        <img src="https://www.gstatic.com/images/branding/product/1x/gmail_2020q4_32dp.png"
             style="width:16px;height:16px;border-radius:3px" alt="Gmail">
        <strong>Gmail conectado</strong>
      </span>
      <div style="display:flex;gap:.5rem;margin-left:auto">
        <button class="gmail-btn gmail-btn--active" onclick="switchSource('gmail')" id="btn-src-gmail">
          📥 Ver Gmail
        </button>
        <button class="gmail-btn gmail-btn--secondary" onclick="switchSource('db')" id="btn-src-db">
          🗄️ Ver BD
        </button>
        <button class="gmail-btn gmail-btn--danger" onclick="disconnectGmail()">
          Desconectar
        </button>
      </div>`;
  } else if (gmailHasCreds) {
    bar.style.display = 'flex';
    bar.innerHTML = `
      <span style="color:var(--fg6);font-size:.8125rem">
        📧 Conecta tu cuenta de Gmail para analizar correos reales
      </span>
      <a href="/gmail/auth" class="gmail-btn gmail-btn--connect" style="margin-left:auto">
        <img src="https://www.gstatic.com/images/branding/product/1x/gmail_2020q4_32dp.png"
             style="width:14px;height:14px;vertical-align:middle;border-radius:2px" alt="">
        Conectar Gmail
      </a>`;
  } else {
    bar.style.display = 'none';
  }
}

// ── Cambiar fuente (Gmail / BD) ────────────────────────────────────────────
async function switchSource(src) {
  currentSource = src;
  selectedId    = null;
  document.getElementById('inbox-empty').classList.remove('hidden');
  document.getElementById('inbox-msg').classList.add('hidden');
  await loadMessages();
}

async function disconnectGmail() {
  await fetch('/gmail/disconnect', { method: 'POST' });
  gmailConnected = false;
  renderGmailBar();
  currentSource  = 'db';
  await loadMessages();
}

// ── Load messages ──────────────────────────────────────────────────────────
async function loadMessages() {
  showListLoading();
  try {
    let endpoint = '/api/inbox';
    if (currentSource === 'gmail' && gmailConnected) endpoint = '/api/gmail/messages';

    const res  = await fetch(endpoint);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    allMessages = (data.messages || []).map(m => ({...m, source: data.source || currentSource}));
    renderList('');
  } catch (err) {
    document.getElementById('msg-list-inner').innerHTML =
      `<div style="padding:2rem;text-align:center;color:var(--fg4);font-size:.875rem">
        ${currentSource === 'gmail'
          ? '❌ No se pudieron cargar los correos de Gmail.<br><small>' + escHtml(err.message) + '</small>'
          : 'Error cargando mensajes'}
       </div>`;
  }
}

function showListLoading() {
  document.getElementById('msg-list-inner').innerHTML = Array(6).fill(`
    <div class="msg-skeleton">
      <div class="msg-skeleton__avatar"></div>
      <div class="msg-skeleton__lines">
        <div class="msg-skeleton__line msg-skeleton__line--title"></div>
        <div class="msg-skeleton__line msg-skeleton__line--sub"></div>
      </div>
    </div>`).join('');
}

// ── Render list ────────────────────────────────────────────────────────────
function renderList(query) {
  const filtered = query
    ? allMessages.filter(m =>
        (m.sender  || '').toLowerCase().includes(query) ||
        (m.subject || '').toLowerCase().includes(query) ||
        (m.body    || '').toLowerCase().includes(query))
    : allMessages;

  const container = document.getElementById('msg-list-inner');

  if (filtered.length === 0) {
    container.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--fg4);font-size:.875rem">Sin resultados</div>';
    return;
  }

  container.innerHTML = filtered.map(m => {
    const isActive = String(m.id) === String(selectedId) ? 'active' : '';
    const color    = avatarColor(m.sender);
    const letter   = avatarLetter(m.sender);
    const preview  = (m.subject || m.body || '').substring(0, 55);
    const date     = formatDate(m.received_at);

    let dot = '';
    if (m.is_spam === true)  dot = '<span class="msg-item__spam-dot" style="background:var(--red)"></span>';
    if (m.is_spam === false) dot = '<span class="msg-item__spam-dot" style="background:var(--green)"></span>';

    const gmailBadge = m.source === 'gmail'
      ? '<span style="font-size:.6rem;background:#ea4335;color:#fff;border-radius:3px;padding:1px 4px;margin-left:4px">Gmail</span>'
      : '';

    return `
      <div class="msg-item ${isActive}" data-id="${escHtml(String(m.id))}" onclick="selectMessage('${escHtml(String(m.id))}')">
        <div class="msg-item__avatar ${color}">${letter}</div>
        <div class="msg-item__content">
          <div class="msg-item__top">
            <span class="msg-item__sender">${escHtml(m.sender || 'Desconocido')}${gmailBadge}</span>
            <span class="msg-item__date">${date}</span>
          </div>
          <div class="msg-item__preview">${escHtml(preview)}</div>
        </div>
        ${dot}
      </div>`;
  }).join('');
}

// ── Select message ─────────────────────────────────────────────────────────
async function selectMessage(id) {
  selectedId = id;
  const msg  = allMessages.find(m => String(m.id) === String(id));
  if (!msg) return;

  document.querySelectorAll('.msg-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === String(id));
  });

  document.getElementById('inbox-empty').classList.add('hidden');
  document.getElementById('inbox-msg').classList.remove('hidden');

  const color  = avatarColor(msg.sender);
  const letter = avatarLetter(msg.sender);
  document.getElementById('msg-avatar').className   = `inbox-msg__avatar ${color}`;
  document.getElementById('msg-avatar').textContent  = letter;
  document.getElementById('msg-sender').textContent  = msg.sender  || 'Desconocido';
  document.getElementById('msg-subject').textContent = msg.subject || '(sin asunto)';
  document.getElementById('msg-body').textContent    = msg.body    || '';
  document.getElementById('msg-date').textContent    = formatDate(msg.received_at);

  document.getElementById('analysis-result').classList.add('hidden');
  document.getElementById('analysis-loading').classList.remove('hidden');
  document.getElementById('analysis-spinner').classList.remove('hidden');

  try {
    let res;
    if (msg.source === 'gmail') {
      // Gmail: analizar directamente con subject + body
      res = await fetch('/api/gmail/analyze', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text: msg.body || '', subject: msg.subject || '' })
      });
    } else {
      // BD / demo: usar ruta con id numérico
      res = await fetch(`/api/inbox/${id}/analyze`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ text: msg.body || msg.subject || '' })
      });
    }

    const data = await res.json();

    const idx = allMessages.findIndex(m => String(m.id) === String(id));
    if (idx >= 0) {
      allMessages[idx].is_spam    = data.is_spam;
      allMessages[idx].confidence = data.confidence;
      allMessages[idx].label      = data.label;
    }
    renderList(document.getElementById('inbox-search').value.toLowerCase());
    renderAnalysis(data);
  } catch {
    document.getElementById('analysis-loading').classList.add('hidden');
    document.getElementById('analysis-spinner').classList.add('hidden');
    document.getElementById('analysis-result').innerHTML =
      '<p style="color:var(--red);font-size:.875rem">Error al analizar. ¿Está corriendo Flask?</p>';
    document.getElementById('analysis-result').classList.remove('hidden');
  }
}

// ── Render analysis result ─────────────────────────────────────────────────
function renderAnalysis(data) {
  document.getElementById('analysis-loading').classList.add('hidden');
  document.getElementById('analysis-spinner').classList.add('hidden');
  document.getElementById('analysis-result').classList.remove('hidden');

  const isSpam = data.is_spam;

  const box   = document.getElementById('analysis-verdict-box');
  const icon  = document.getElementById('analysis-icon');
  const label = document.getElementById('analysis-label');
  const badge = document.getElementById('analysis-badge');
  const fill  = document.getElementById('analysis-fill');
  const conf  = document.getElementById('analysis-conf');

  box.className     = `analysis-verdict analysis-verdict--${isSpam ? 'spam' : 'ham'}`;
  icon.textContent  = isSpam ? '⚠️' : '✅';
  label.className   = `analysis-verdict__label av-label-${isSpam ? 'spam' : 'ham'}`;
  label.textContent = isSpam ? 'Spam' : 'No Spam';
  badge.className   = `confidence-badge confidence-badge--${isSpam ? 'spam' : 'ham'}`;
  badge.textContent = `${data.confidence}% Confianza`;
  fill.className    = `confidence-fill confidence-fill--${isSpam ? 'spam' : 'ham'}`;
  conf.textContent  = `${data.confidence}%`;
  conf.style.color  = isSpam ? 'var(--red)' : 'var(--green)';

  fill.style.width = '0%';
  requestAnimationFrame(() => setTimeout(() => { fill.style.width = data.confidence + '%'; }, 40));

  document.getElementById('analysis-ham-pct').textContent  = `${data.ham_prob}% HAM`;
  document.getElementById('analysis-spam-pct').textContent = `${data.spam_prob}% SPAM`;

  const signals     = data.spam_signals || [];
  const signalsWrap = document.getElementById('analysis-signals-wrap');
  const noSignals   = document.getElementById('analysis-no-signals');
  const signalsList = document.getElementById('analysis-signals-list');

  if (signals.length > 0) {
    signalsWrap.classList.remove('hidden');
    noSignals.classList.add('hidden');
    signalsList.innerHTML = signals.map(s => `
      <div class="signal-chip">
        <span class="signal-chip__icon">${SIGNAL_ICONS[s.type] || '🔍'}</span>
        <div>
          <div class="signal-chip__label">${s.label}</div>
          <div class="signal-chip__detail">${s.detail}</div>
        </div>
      </div>`).join('');
  } else {
    signalsWrap.classList.add('hidden');
    noSignals.classList.remove('hidden');
  }

  document.getElementById('analysis-tokens').textContent = data.clean_text || '(sin tokens)';

  const result = document.getElementById('analysis-result');
  result.style.opacity    = '0';
  result.style.transform  = 'translateY(8px)';
  result.style.transition = 'opacity .25s ease, transform .25s ease';
  requestAnimationFrame(() => { result.style.opacity='1'; result.style.transform='translateY(0)'; });
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  const t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = `position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;
    padding:.6rem 1.1rem;border-radius:.5rem;font-size:.875rem;font-weight:500;
    background:${type==='ok'?'var(--green)':'var(--red)'};color:#fff;
    box-shadow:0 4px 12px rgba(0,0,0,.3);transition:opacity .4s`;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; setTimeout(() => t.remove(), 400); }, 3000);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function formatDate(raw) {
  if (!raw) return '';
  if (typeof raw === 'string' && raw.length < 12) return raw;
  try {
    const d   = new Date(raw);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 86400)  return d.toLocaleTimeString('es-MX', { hour:'2-digit', minute:'2-digit' });
    if (diff < 604800) return d.toLocaleDateString('es-MX', { weekday:'short' });
    return d.toLocaleDateString('es-MX', { day:'numeric', month:'short' });
  } catch { return raw; }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
