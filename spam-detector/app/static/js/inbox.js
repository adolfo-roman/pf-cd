// inbox.js — panel estilo Google Messages con análisis automático

const SIGNAL_ICONS = { keywords:'🔤', uppercase:'🔠', phone:'📞', url:'🔗', money:'💰', exclamation:'❗' };

// Colores de avatar basados en inicial
const AV_COLORS = ['av-blue','av-red','av-green','av-purple','av-orange','av-teal','av-pink'];
function avatarColor(name) {
  let h = 0;
  for (const c of (name || 'X')) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
  return AV_COLORS[Math.abs(h) % AV_COLORS.length];
}
function avatarLetter(name) { return (name || '?')[0].toUpperCase(); }

let allMessages  = [];
let selectedId   = null;

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await checkDbStatus();
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
      bar.style.cssText += ';padding:.5rem 1rem;border-radius:.5rem;font-size:.8125rem;font-family:monospace;display:flex;align-items:center;gap:.6rem;margin-bottom:1rem';
      bar.innerHTML = `✅ BD conectada — ${data.host} · ${data.db} · ${data.latency_ms}ms`;
    } else {
      bar.className = 'db-bar-warn';
      bar.style.cssText += ';padding:.5rem 1rem;border-radius:.5rem;font-size:.8125rem;font-family:monospace;display:flex;align-items:center;gap:.6rem;margin-bottom:1rem';
      bar.innerHTML = `⚠️ BD no configurada — mostrando datos demo. <span style="color:var(--fg6);margin-left:.5rem">Edita el archivo .env con tus credenciales.</span>`;
    }
  } catch {
    bar.style.display = 'none';
  }
}

// ── Load messages ──────────────────────────────────────────────────────────
async function loadMessages() {
  try {
    const res  = await fetch('/api/inbox');
    const data = await res.json();
    allMessages = data.messages || [];
    renderList('');
  } catch (err) {
    document.getElementById('msg-list-inner').innerHTML =
      '<div style="padding:2rem;text-align:center;color:var(--fg4);font-size:.875rem">Error cargando mensajes</div>';
  }
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
    const isActive = m.id === selectedId ? 'active' : '';
    const color    = avatarColor(m.sender);
    const letter   = avatarLetter(m.sender);
    const preview  = (m.subject || m.body || '').substring(0, 55);
    const date     = formatDate(m.received_at);

    // Indicador de resultado si ya fue analizado
    let dot = '';
    if (m.is_spam === true)  dot = '<span class="msg-item__spam-dot" style="background:var(--red)"></span>';
    if (m.is_spam === false) dot = '<span class="msg-item__spam-dot" style="background:var(--green)"></span>';

    return `
      <div class="msg-item ${isActive}" data-id="${m.id}" onclick="selectMessage(${m.id})">
        <div class="msg-item__avatar ${color}">${letter}</div>
        <div class="msg-item__content">
          <div class="msg-item__top">
            <span class="msg-item__sender">${escHtml(m.sender || 'Desconocido')}</span>
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
  const msg  = allMessages.find(m => m.id === id);
  if (!msg) return;

  // Highlight activo en lista
  document.querySelectorAll('.msg-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.id) === id);
  });

  // Mostrar panel derecho
  document.getElementById('inbox-empty').classList.add('hidden');
  document.getElementById('inbox-msg').classList.remove('hidden');

  // Rellenar header y cuerpo
  const color  = avatarColor(msg.sender);
  const letter = avatarLetter(msg.sender);
  document.getElementById('msg-avatar').className  = `inbox-msg__avatar ${color}`;
  document.getElementById('msg-avatar').textContent = letter;
  document.getElementById('msg-sender').textContent  = msg.sender  || 'Desconocido';
  document.getElementById('msg-subject').textContent = msg.subject || '(sin asunto)';
  document.getElementById('msg-body').textContent    = msg.body    || '';
  document.getElementById('msg-date').textContent    = formatDate(msg.received_at);

  // Ocultar resultado anterior, mostrar loading
  document.getElementById('analysis-result').classList.add('hidden');
  document.getElementById('analysis-loading').classList.remove('hidden');
  document.getElementById('analysis-spinner').classList.remove('hidden');

  // Analizar automáticamente
  try {
    const res  = await fetch(`/api/inbox/${id}/analyze`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ text: msg.body || msg.subject || '' })
    });
    const data = await res.json();

    // Actualizar cache local con resultado
    const idx = allMessages.findIndex(m => m.id === id);
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

  // Verdict box
  const box   = document.getElementById('analysis-verdict-box');
  const icon  = document.getElementById('analysis-icon');
  const label = document.getElementById('analysis-label');
  const badge = document.getElementById('analysis-badge');
  const fill  = document.getElementById('analysis-fill');
  const conf  = document.getElementById('analysis-conf');

  box.className    = `analysis-verdict analysis-verdict--${isSpam ? 'spam' : 'ham'}`;
  icon.textContent = isSpam ? '⚠️' : '✅';
  label.className  = `analysis-verdict__label av-label-${isSpam ? 'spam' : 'ham'}`;
  label.textContent= isSpam ? 'Spam' : 'No Spam';
  badge.className  = `confidence-badge confidence-badge--${isSpam ? 'spam' : 'ham'}`;
  badge.textContent= `${data.confidence}% Confianza`;
  fill.className   = `confidence-fill confidence-fill--${isSpam ? 'spam' : 'ham'}`;
  conf.textContent = `${data.confidence}%`;
  conf.style.color = isSpam ? 'var(--red)' : 'var(--green)';

  // Animar barra
  fill.style.width = '0%';
  requestAnimationFrame(() => setTimeout(() => { fill.style.width = data.confidence + '%'; }, 40));

  // Porcentajes
  document.getElementById('analysis-ham-pct').textContent  = `${data.ham_prob}% HAM`;
  document.getElementById('analysis-spam-pct').textContent = `${data.spam_prob}% SPAM`;

  // Señales
  const signals      = data.spam_signals || [];
  const signalsWrap  = document.getElementById('analysis-signals-wrap');
  const noSignals    = document.getElementById('analysis-no-signals');
  const signalsList  = document.getElementById('analysis-signals-list');

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

  // Tokens NLP
  document.getElementById('analysis-tokens').textContent = data.clean_text || '(sin tokens)';

  // Animación entrada
  const result = document.getElementById('analysis-result');
  result.style.opacity   = '0';
  result.style.transform = 'translateY(8px)';
  result.style.transition = 'opacity .25s ease, transform .25s ease';
  requestAnimationFrame(() => { result.style.opacity='1'; result.style.transform='translateY(0)'; });
}

// ── Helpers ────────────────────────────────────────────────────────────────
function formatDate(raw) {
  if (!raw) return '';
  // Si ya es string corto (demo), devolver tal cual
  if (typeof raw === 'string' && raw.length < 12) return raw;
  try {
    const d = new Date(raw);
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
