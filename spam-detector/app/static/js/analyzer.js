// analyzer.js — conecta con /api/predict y muestra señales de spam

const textarea   = document.getElementById('sms-input');
const charCountEl= document.getElementById('char-count');
const analyzeBtn = document.getElementById('analyze-btn');
const clearBtn   = document.getElementById('clear-btn');
const btnText    = document.getElementById('btn-text');
const btnSend    = document.getElementById('btn-send-icon');
const btnSpin    = document.getElementById('btn-spin-icon');

const panelIdle    = document.getElementById('result-idle');
const panelLoading = document.getElementById('result-loading');
const panelVerdict = document.getElementById('result-verdict');

// Íconos por tipo de señal
const SIGNAL_ICONS = {
  keywords:    '🔤',
  uppercase:   '🔠',
  phone:       '📞',
  url:         '🔗',
  money:       '💰',
  exclamation: '❗',
};

// Counter
textarea.addEventListener('input', () => { charCountEl.textContent = textarea.value.length; });

// Limpiar
clearBtn.addEventListener('click', () => {
  textarea.value = '';
  charCountEl.textContent = 0;
  showIdle();
});

// Ejemplos
function setExample(btn) {
  const text = btn.textContent.replace('💬', '').trim();
  textarea.value = text;
  charCountEl.textContent = text.length;
}
window.setExample = setExample;

// Analizar con Ctrl+Enter
analyzeBtn.addEventListener('click', analyze);
textarea.addEventListener('keydown', e => { if (e.ctrlKey && e.key === 'Enter') analyze(); });

async function analyze() {
  const text = textarea.value.trim();
  if (!text) { textarea.focus(); return; }

  showLoading();

  try {
    const res  = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();

    if (data.error) { showIdle(); alert('Error: ' + data.error); return; }

    showVerdict(data);

    // Guardar en historial de sesión
    const hist = JSON.parse(sessionStorage.getItem('aegis_history') || '[]');
    hist.unshift({
      id: Date.now(),
      text: text.substring(0, 80) + (text.length > 80 ? '...' : ''),
      classification: data.is_spam ? 'Spam' : 'No Spam',
      confidence: data.confidence,
      date: new Date().toISOString().split('T')[0],
      time: new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
    });
    if (hist.length > 50) hist.pop();
    sessionStorage.setItem('aegis_history', JSON.stringify(hist));

  } catch (err) {
    showIdle();
    alert('Error de red. ¿Está corriendo Flask?');
  }
}

// ── Estados ────────────────────────────────────────────────────────────────
function showIdle() {
  panelIdle.classList.remove('hidden');
  panelLoading.classList.add('hidden');
  panelVerdict.classList.add('hidden');
  setBtn(false);
}

function showLoading() {
  panelIdle.classList.add('hidden');
  panelLoading.classList.remove('hidden');
  panelVerdict.classList.add('hidden');
  setBtn(true);
}

function setBtn(loading) {
  analyzeBtn.disabled = loading;
  btnText.textContent = loading ? 'Analizando...' : 'Analizar Mensaje';
  btnSend.classList.toggle('hidden', loading);
  btnSpin.classList.toggle('hidden', !loading);
}

// ── Render veredicto ────────────────────────────────────────────────────────
function showVerdict(data) {
  panelLoading.classList.add('hidden');
  panelIdle.classList.add('hidden');
  panelVerdict.classList.remove('hidden');
  setBtn(false);

  const isSpam = data.is_spam;

  // Verdict box
  const box   = document.getElementById('verdict-box');
  const icon  = document.getElementById('verdict-icon');
  const label = document.getElementById('verdict-label');
  const badge = document.getElementById('confidence-badge');
  const fill  = document.getElementById('confidence-fill');
  const val   = document.getElementById('confidence-val');

  box.className    = `verdict-box verdict-box--${isSpam ? 'spam' : 'ham'}`;
  icon.className   = `verdict-icon-wrap verdict-icon-wrap--${isSpam ? 'spam' : 'ham'}`;
  icon.textContent = isSpam ? '⚠️' : '✅';
  label.className  = `verdict-label verdict-label--${isSpam ? 'spam' : 'ham'}`;
  label.textContent= isSpam ? 'Spam' : 'No Spam';
  badge.className  = `confidence-badge confidence-badge--${isSpam ? 'spam' : 'ham'}`;
  badge.textContent= `${data.confidence}% Confianza`;
  fill.className   = `confidence-fill confidence-fill--${isSpam ? 'spam' : 'ham'}`;
  val.textContent  = `${data.confidence}%`;

  // Animar barra
  fill.style.width = '0%';
  requestAnimationFrame(() => setTimeout(() => { fill.style.width = data.confidence + '%'; }, 50));

  // ── Panel de señales ────────────────────────────────────────────────────
  const signalsPanel   = document.getElementById('signals-panel');
  const noSignalsPanel = document.getElementById('no-signals-panel');
  const signalsList    = document.getElementById('signals-list');
  const signals        = data.spam_signals || [];

  if (signals.length > 0) {
    signalsPanel.classList.remove('hidden');
    noSignalsPanel.classList.add('hidden');
    signalsList.innerHTML = signals.map(s => `
      <div class="signal-chip">
        <span class="signal-chip__icon">${SIGNAL_ICONS[s.type] || '🔍'}</span>
        <div>
          <div class="signal-chip__label">${s.label}</div>
          <div class="signal-chip__detail">${s.detail}</div>
        </div>
      </div>
    `).join('');
  } else {
    signalsPanel.classList.add('hidden');
    noSignalsPanel.classList.remove('hidden');
  }

  // Stats
  const st = data.stats;
  document.getElementById('stat-chars').textContent = st.num_chars;
  document.getElementById('stat-upper').textContent = st.num_uppercase;
  document.getElementById('stat-digits').textContent= st.num_digits;
  document.getElementById('stat-ratio').textContent = `${st.ratio_uppercase}%`;

  // Texto procesado
  document.getElementById('clean-text').textContent = data.clean_text || '(sin tokens tras NLP)';

  // Reset feedback
  document.getElementById('fb-correct').classList.remove('correct');
  document.getElementById('fb-incorrect').classList.remove('incorrect');
  document.getElementById('feedback-msg').classList.add('hidden');

  // Animación de entrada
  panelVerdict.style.opacity   = '0';
  panelVerdict.style.transform = 'translateY(12px)';
  panelVerdict.style.transition = 'opacity .3s ease, transform .3s ease';
  requestAnimationFrame(() => {
    panelVerdict.style.opacity   = '1';
    panelVerdict.style.transform = 'translateY(0)';
  });
}

// Feedback
function setFeedback(type) {
  document.getElementById('fb-correct').classList.remove('correct');
  document.getElementById('fb-incorrect').classList.remove('incorrect');
  document.getElementById(`fb-${type}`).classList.add(type);
  document.getElementById('feedback-msg').classList.remove('hidden');
}
window.setFeedback = setFeedback;
