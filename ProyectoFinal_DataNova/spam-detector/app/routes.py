"""
routes.py — Rutas Flask: páginas + API REST
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash
from functools import wraps

from .predictor import predict_message
from .database  import (check_connection, get_inbox_messages, save_analysis,
                         ensure_tables, seed_demo_messages,
                         create_user, get_user_by_email,
                         get_user_stats, get_user_recent_analyses,
                         get_user_weekly_activity, get_user_all_analyses)

main = Blueprint('main', __name__)

DATA_DIR          = Path(__file__).resolve().parents[1] / 'data'
FEEDBACK_FILE     = DATA_DIR / 'feedback.csv'
PENDING_OAUTH_FILE = DATA_DIR / 'pending_oauth_users.txt'


def _log_pending_oauth_user(email: str, name: str) -> None:
    """Registra el correo del nuevo usuario para añadirlo manualmente en Google Cloud."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    with open(PENDING_OAUTH_FILE, 'a', encoding='utf-8') as f:
        f.write(f'{timestamp} | {email} | {name}\n')


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


def _append_feedback_example(actual_label: str, text: str, predicted_label: str, feedback_type: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = FEEDBACK_FILE.exists()
    with open(FEEDBACK_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['v1', 'v2', 'predicted_label', 'feedback', 'timestamp'],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'v1': actual_label,
            'v2': text,
            'predicted_label': predicted_label,
            'feedback': feedback_type,
            'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        })


# ── Páginas ───────────────────────────────────────────────────────────────
# Añadir decorador para login requerido
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Por favor inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

# MODIFICAR la ruta '/' - AHORA ES LA LANDING PAGE
@main.route('/')
def landing():
    """Landing page pública"""
    return render_template('landing/index.html')

@main.route('/index')
def index():
    """Alias para compatibilidad con enlaces antiguos."""
    return redirect(url_for('main.landing'))

# NUEVA RUTA: Login / Registro (GET y POST)
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action   = request.form.get('action', 'login')   # 'login' | 'register'
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        name     = request.form.get('name', '').strip()

        if not email or not password:
            flash('Correo y contraseña son requeridos.', 'error')
            return render_template('auth/login.html', show_register=(action == 'register'))

        # ── Registro ──────────────────────────────────────────────────────
        if action == 'register':
            if len(password) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'error')
                return render_template('auth/login.html', show_register=True)
            try:
                from werkzeug.security import generate_password_hash
                ensure_tables()
                if get_user_by_email(email):
                    flash('Ya existe una cuenta con ese correo.', 'error')
                    return render_template('auth/login.html', show_register=True)

                display_name = name if name else email.split('@')[0]
                user_id = create_user(email, display_name, generate_password_hash(password))

                # Registrar email para alta manual en Google Cloud OAuth
                _log_pending_oauth_user(email, display_name)

                session['logged_in'] = True
                session['user_id']    = user_id
                session['user_email'] = email
                session['user_name']  = display_name
                flash(f'¡Cuenta creada! Bienvenido/a, {display_name}.', 'success')
                return redirect(url_for('main.analyzer'))
            except Exception as e:
                flash(f'Error al crear cuenta: {str(e)[:100]}', 'error')
                return render_template('auth/login.html', show_register=True)

        # ── Login ─────────────────────────────────────────────────────────
        else:
            try:
                from werkzeug.security import check_password_hash
                ensure_tables()
                user = get_user_by_email(email)
                if not user or not check_password_hash(user['password_hash'], password):
                    flash('Correo o contraseña incorrectos.', 'error')
                    return render_template('auth/login.html')
                if not user.get('is_active'):
                    flash('Cuenta desactivada. Contacta al administrador.', 'error')
                    return render_template('auth/login.html')

                if request.form.get('remember') == 'on':
                    session.permanent = True
                session['logged_in'] = True
                session['user_id']    = user['id']
                session['user_email'] = email
                session['user_name']  = user.get('name') or email.split('@')[0]
                flash(f'¡Bienvenido/a de nuevo, {session["user_name"]}!', 'success')
                return redirect(url_for('main.analyzer'))
            except Exception as e:
                flash(f'Error al iniciar sesión: {str(e)[:100]}', 'error')

    show_register = request.args.get('register') == '1'
    return render_template('auth/login.html', show_register=show_register)

# NUEVA RUTA: Logout
@main.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('main.landing'))

# MODIFICAR analyzer - AHORA REQUIERE LOGIN
@main.route('/analyzer')
@login_required
def analyzer():
    return render_template('analyzer.html')

# MODIFICAR dashboard - REQUIERE LOGIN
@main.route('/dashboard')
@login_required
def dashboard():
    metrics  = _aggregate_metrics()
    user_id  = session.get('user_id')

    stats           = {'total': 0, 'spam': 0, 'ham': 0, 'accuracy': 0.0}
    recent_analyses = []
    weekly_data     = []

    if user_id:
        try:
            ensure_tables()
            stats           = get_user_stats(user_id)
            recent_analyses = get_user_recent_analyses(user_id, limit=5)
            weekly_data     = get_user_weekly_activity(user_id)
        except Exception:
            pass

    total   = stats['total']
    spam    = stats['spam']
    ham     = stats['ham']
    ham_pct = round(ham / total * 100, 1) if total > 0 else 0.0

    return render_template('dashboard.html',
        metrics=metrics,
        stats=stats,
        ham_pct=ham_pct,
        recent_analyses=recent_analyses,
        weekly_data=weekly_data,
    )

# MODIFICAR inbox - REQUIERE LOGIN
@main.route('/inbox')
@login_required
def inbox():
    return render_template('inbox.html')

# MODIFICAR history - REQUIERE LOGIN
@main.route('/history')
@login_required
def history():
    return render_template('history.html')


@main.route('/history/export')
@login_required
def history_export():
    import csv
    import io
    from flask import Response
    user_id = session.get('user_id')
    rows = get_user_all_analyses(user_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Fecha', 'Clasificación', 'Confianza (%)', 'Texto'])
    for r in rows:
        date_str = r['analyzed_at'].strftime('%Y-%m-%d %H:%M:%S') if r.get('analyzed_at') else ''
        writer.writerow([
            date_str,
            'Spam' if r.get('is_spam') else 'No Spam',
            round(float(r.get('confidence', 0)) * 100, 1) if r.get('confidence', 0) <= 1 else round(float(r.get('confidence', 0)), 1),
            r.get('clean_text', '')
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="historial_datanova.csv"'}
    )

# MODIFICAR about - REQUIERE LOGIN
@main.route('/about')
@login_required
def about():
    return render_template('about.html')

# NUEVA RUTA: Landing sections (para scroll suave)
@main.route('/landing-section/<section>')
def landing_section(section):
    """Endpoint para cargar secciones individuales de la landing (opcional)"""
    return render_template(f'landing/partials/{section}.html')


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

    # Guardar en BD con user_id de la sesión activa
    inbox_id = data.get('inbox_id')
    user_id  = session.get('user_id')
    save_analysis(inbox_id, result, user_id)

    return jsonify(result)


# ── API: estado de la BD y el modelo ────────────────────────────────────
@main.route('/api/status')
def api_status():
    db_ok = False
    db_msg = ''
    try:
        check_connection()
        db_ok = True
    except Exception as e:
        db_msg = str(e)[:120]

    model_ok = False
    model_msg = ''
    try:
        from .predictor import predict_message
        model_ok = True
    except Exception as e:
        model_msg = str(e)[:200]

    status = 200 if db_ok else 503
    return jsonify({
        'db':    'ok' if db_ok else f'error: {db_msg}',
        'model': 'ok' if model_ok else f'error: {model_msg}',
    }), status


# ── API: retroalimentación ───────────────────────────────────────────────
@main.route('/api/feedback', methods=['POST'])
def api_feedback():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    predicted_label = (data.get('predicted_label') or '').strip().lower()
    feedback_type = (data.get('feedback') or '').strip().lower()

    if not text:
        return jsonify({'error': 'El campo "text" es obligatorio.'}), 400
    if predicted_label not in {'spam', 'ham'}:
        return jsonify({'error': 'predicted_label debe ser "spam" o "ham".'}), 400
    if feedback_type not in {'correct', 'incorrect'}:
        return jsonify({'error': 'feedback debe ser "correct" o "incorrect".'}), 400

    actual_label = predicted_label if feedback_type == 'correct' else ('ham' if predicted_label == 'spam' else 'spam')
    try:
        _append_feedback_example(actual_label, text, predicted_label, feedback_type)
    except Exception as exc:
        return jsonify({'error': f'No se pudo guardar la retroalimentación: {exc}'}), 500

    return jsonify({
        'ok': True,
        'message': 'Retroalimentación guardada para el próximo reentrenamiento.',
        'actual_label': actual_label,
        'predicted_label': predicted_label,
        'feedback': feedback_type,
    })


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


# ── Gmail OAuth ───────────────────────────────────────────────────────────
@main.route('/gmail/auth')
def gmail_auth():
    try:
        from .gmail import get_auth_url, has_credentials
        if not has_credentials():
            return jsonify({'error': 'Falta credentials.json. Descárgalo desde Google Cloud Console.'}), 400
        from .gmail import get_redirect_uri
        redirect_uri = get_redirect_uri()
        return redirect(get_auth_url(redirect_uri))
    except ImportError:
        return jsonify({'error': 'Instala google-auth-oauthlib: pip install google-auth-oauthlib google-api-python-client'}), 500


@main.route('/gmail/callback')
def gmail_callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('main.inbox') + '?gmail_error=1')
    try:
        from .gmail import exchange_code, get_redirect_uri
        redirect_uri = get_redirect_uri()
        user_id = session.get('user_id')
        exchange_code(code, redirect_uri, user_id)
        return redirect(url_for('main.inbox') + '?gmail_ok=1')
    except Exception as e:
        return redirect(url_for('main.inbox') + f'?gmail_error=1&msg={str(e)[:60]}')


@main.route('/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    try:
        from .gmail import disconnect
        disconnect(session.get('user_id'))
    except Exception:
        pass
    return jsonify({'ok': True})


# ── API: estado de Gmail ──────────────────────────────────────────────────
@main.route('/api/gmail/status')
def api_gmail_status():
    try:
        from .gmail import is_connected, has_credentials
        user_id = session.get('user_id')
        return jsonify({
            'connected':       is_connected(user_id),
            'has_credentials': has_credentials(),
        })
    except ImportError:
        return jsonify({'connected': False, 'has_credentials': False,
                        'error': 'Instala: pip install google-auth-oauthlib google-api-python-client'})


# ── API: mensajes de Gmail ────────────────────────────────────────────────
@main.route('/api/gmail/messages')
def api_gmail_messages():
    try:
        from .gmail import get_messages
        user_id  = session.get('user_id')
        messages = get_messages(max_results=25, user_id=user_id)
        return jsonify({'source': 'gmail', 'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: analizar mensaje de Gmail ────────────────────────────────────────
@main.route('/api/gmail/analyze', methods=['POST'])
def api_gmail_analyze():
    data    = request.get_json(force=True, silent=True) or {}
    text    = (data.get('text') or '').strip()
    subject = (data.get('subject') or '').strip()

    if not text and not subject:
        return jsonify({'error': 'Se requiere text o subject'}), 400

    # Combinar subject + body para mejor análisis
    combined = f"{subject}\n{text}".strip() if subject else text
    if len(combined) > 2000:
        combined = combined[:2000]

    result = predict_message(combined)
    # Guardar sin inbox_id (mensaje Gmail, no en nuestra BD de inbox)
    save_analysis(None, result)
    return jsonify(result)
