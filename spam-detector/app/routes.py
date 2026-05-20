"""
routes.py — Rutas Flask: páginas + API REST
"""

import csv
import json
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify

from .predictor import predict_message
from .database  import check_connection, get_inbox_messages, save_analysis, ensure_tables, seed_demo_messages

main = Blueprint('main', __name__)

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


# ── Helpers métricas ──────────────────────────────────────────────────────
def _load_experiment_results():
    results = []
    path = DATA_DIR / 'experiment_results.csv'
    if not path.exists():
        return results
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            results.append(row)
    return results


def _aggregate_metrics():
    rows = _load_experiment_results()
    models = {}
    for r in rows:
        name = r['model_name']
        if name not in models:
            models[name] = {'accuracy': [], 'precision': [], 'recall': [], 'f1_score': [], 'auc': []}
        for metric in models[name]:
            try:
                models[name][metric].append(float(r[metric]))
            except (ValueError, KeyError):
                pass
    aggregated = []
    for name, metrics in models.items():
        avg = {k: round(sum(v)/len(v)*100, 2) if v else 0 for k, v in metrics.items()}
        aggregated.append({'model': name, **avg})
    aggregated.sort(key=lambda x: x['f1_score'], reverse=True)
    return aggregated


# ── Páginas ───────────────────────────────────────────────────────────────
@main.route('/')
def index():
    return render_template('index.html')

@main.route('/dashboard')
def dashboard():
    metrics = _aggregate_metrics()
    return render_template('dashboard.html', metrics=metrics)

@main.route('/inbox')
def inbox():
    return render_template('inbox.html')

@main.route('/history')
def history():
    return render_template('history.html')

@main.route('/about')
def about():
    return render_template('about.html')


# ── API: predicción ───────────────────────────────────────────────────────
@main.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()

    if not text:
        return jsonify({'error': 'El campo "text" es obligatorio.'}), 400
    if len(text) > 2000:
        return jsonify({'error': 'Texto demasiado largo (máx. 2000 caracteres).'}), 400

    result = predict_message(text)

    # Intentar guardar en BD si está configurada (silencioso si falla)
    inbox_id = data.get('inbox_id')
    save_analysis(inbox_id, result)

    return jsonify(result)


# ── API: estado de la BD ──────────────────────────────────────────────────
@main.route('/api/db-status')
def api_db_status():
    return jsonify(check_connection())


# ── API: inbox de mensajes ────────────────────────────────────────────────
@main.route('/api/inbox')
def api_inbox():
    """Devuelve mensajes del inbox desde la BD o datos demo si no hay BD."""
    try:
        ensure_tables()
        seed_demo_messages()
        messages = get_inbox_messages(limit=50)
        return jsonify({'source': 'database', 'messages': messages})
    except Exception as e:
        # Sin BD: devolver mensajes demo hardcodeados
        demo = _demo_messages()
        return jsonify({'source': 'demo', 'messages': demo, 'db_error': str(e)})


@main.route('/api/inbox/<int:msg_id>/analyze', methods=['POST'])
def api_inbox_analyze(msg_id):
    """Analiza un mensaje específico del inbox."""
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Se requiere el campo text'}), 400

    result = predict_message(text)
    save_analysis(msg_id, result)
    return jsonify(result)


# ── API: métricas ─────────────────────────────────────────────────────────
@main.route('/api/metrics')
def api_metrics():
    return jsonify(_aggregate_metrics())


# ── Demo messages (cuando no hay BD) ─────────────────────────────────────
def _demo_messages():
    import datetime
    msgs = [
        (1,  'Telcel',        'Hoy te damos más',           'Hoy te damos más Gigas GRATIS. Activa tu bono antes del domingo en telcel.com/bono',              'Sun',    False),
        (2,  'TELCEL',        'Ademas puedes hacer tu...',  'Además, puedes hacer tu recarga doble este fin de semana llamando al 800-123-4567',                'May 11', False),
        (3,  'TelcelAmzn',    'Amazon: Tu recarga incluye', 'Amazon Prime incluido en tu plan. Actívalo GRATIS hoy en amzn.to/telcel',                           'Mar 11', False),
        (4,  'UNOTV.COM',     'ANTE PRESION EXTERNA',       'ANTE PRESION EXTERNA: El gobierno confirmó nueva política. Lee más en unotv.com',                  'Feb 19', False),
        (5,  'ClaroPay',      'Tu paquete de datos esta...','Tu paquete de datos está por vencer. Recarga AHORA y obtén el doble. Tiempo limitado.',            'Feb 14', False),
        (6,  'Google',        'Security alert',             'A new sign-in on Windows. If this was you, you can ignore this message.',                           'Feb 10', False),
        (7,  'Banco Azteca',  'Alerta de seguridad',        'URGENTE: Tu cuenta fue bloqueada. Verifica tus datos en bit.ly/azteca-verify AHORA.',              'Feb 5',  False),
        (8,  'Papá',          'Para la cena',               '¿Ya confirmaste si vas a venir a cenar el domingo? Tu mamá quiere saber cuántos somos.',           'Feb 3',  False),
        (9,  'IMSS Digital',  'Apoyo económico',            'Tienes $3,500 pesos de apoyo disponibles. Regístrate GRATIS en imss-apoyos.com hoy.',              'Jan 28', False),
        (10, 'Ana García',    'Reunión del jueves',         'Hola, confirmo asistencia a la reunión del jueves a las 10 AM en sala 3. Saludos.',                'Jan 25', False),
    ]
    return [
        {'id': id_, 'sender': s, 'subject': sub, 'body': body,
         'received_at': date, 'is_read': read,
         'label': None, 'confidence': None, 'is_spam': None}
        for id_, s, sub, body, date, read in msgs
    ]
