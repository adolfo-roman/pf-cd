// history.js — lee sessionStorage y renderiza el historial

const DEFAULT_ITEMS = [
  { id: 1, text: 'Felicidades! Has ganado un iPhone...', classification: 'Spam', confidence: 98, date: '2026-05-17', time: '14:30' },
  { id: 2, text: 'Hola, confirmo nuestra reunión...', classification: 'No Spam', confidence: 94, date: '2026-05-17', time: '12:15' },
  { id: 3, text: 'URGENTE: Tu cuenta será suspendida...', classification: 'Spam', confidence: 99, date: '2026-05-17', time: '09:45' },
  { id: 4, text: 'Buenos días equipo, adjunto el reporte...', classification: 'No Spam', confidence: 97, date: '2026-05-16', time: '18:20' },
  { id: 5, text: 'Haz clic aquí para reclamar tu premio...', classification: 'Spam', confidence: 96, date: '2026-05-16', time: '15:10' },
  { id: 6, text: 'Recordatorio: pago de factura pendiente...', classification: 'No Spam', confidence: 92, date: '2026-05-16', time: '11:30' },
  { id: 7, text: 'Has sido seleccionado para una oferta exclusiva...', classification: 'Spam', confidence: 97, date: '2026-05-15', time: '16:45' },
  { id: 8, text: 'Gracias por tu compra. Orden confirmada...', classification: 'No Spam', confidence: 95, date: '2026-05-15', time: '10:20' },
  { id: 9, text: 'Verificación requerida: actualiza tus datos...', classification: 'Spam', confidence: 93, date: '2026-05-14', time: '14:15' },
  { id: 10, text: 'Hola mamá, te llamo luego...', classification: 'No Spam', confidence: 99, date: '2026-05-14', time: '09:30' },
];

function getItems() {
  try {
    const stored = JSON.parse(sessionStorage.getItem('aegis_history') || '[]');
    return stored.length > 0 ? stored : DEFAULT_ITEMS;
  } catch { return DEFAULT_ITEMS; }
}

function render() {
  const items   = getItems();
  const search  = document.getElementById('search-input').value.toLowerCase();
  const filter  = document.getElementById('filter-select').value;

  const filtered = items.filter(item => {
    const matchSearch = item.text.toLowerCase().includes(search);
    const matchFilter = filter === 'all' ||
      (filter === 'spam' && item.classification === 'Spam') ||
      (filter === 'ham'  && item.classification === 'No Spam');
    return matchSearch && matchFilter;
  });

  // Update mini stats
  const spam   = items.filter(i => i.classification === 'Spam').length;
  const ham    = items.filter(i => i.classification === 'No Spam').length;
  const avgC   = Math.round(items.reduce((s, i) => s + i.confidence, 0) / items.length);
  document.getElementById('h-total').textContent = items.length;
  document.getElementById('h-spam').textContent  = spam;
  document.getElementById('h-ham').textContent   = ham;
  document.getElementById('h-avg').textContent   = avgC + '%';

  const list  = document.getElementById('history-list');
  const empty = document.getElementById('empty-state');

  if (filtered.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  list.innerHTML = filtered.map(item => {
    const isSpam = item.classification === 'Spam';
    return `
      <div class="history-item">
        <div class="history-item__icon history-item__icon--${isSpam ? 'spam' : 'ham'}">
          ${isSpam ? '⚠️' : '✅'}
        </div>
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.25rem">
            <span class="recent-item__badge ${isSpam ? 'badge-spam' : 'badge-ham'}">${item.classification}</span>
            <span style="font-size:.8125rem;color:var(--fg6)">${item.confidence}% confianza</span>
          </div>
          <div class="history-item__text">${item.text}</div>
          <div class="history-item__date">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            ${item.date} · ${item.time}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  render();
  document.getElementById('search-input').addEventListener('input', render);
  document.getElementById('filter-select').addEventListener('change', render);
});
