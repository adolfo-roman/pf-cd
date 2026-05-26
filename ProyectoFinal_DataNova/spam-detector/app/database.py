"""
database.py — Conexión PostgreSQL y operaciones de la BD
Carga credenciales desde .env (python-dotenv).
Si la BD no está configurada, la app sigue funcionando en modo "sin BD".
"""

import os
import json
from pathlib import Path
from datetime import datetime

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except ImportError:
    pass

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


def _get_conn_params() -> dict:
    return {
        'user':     os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'host':     os.getenv('DB_HOST'),
        'port':     os.getenv('DB_PORT', '5432'),
        'dbname':   os.getenv('DB_NAME'),
        'sslmode':  os.getenv('DB_SSLMODE', 'require'),
        'connect_timeout': 5,
    }


def _is_configured() -> bool:
    p = _get_conn_params()
    return all([p['user'], p['password'], p['host'], p['dbname']])


def get_connection():
    """Devuelve conexión psycopg2 o lanza excepción con mensaje claro."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError('psycopg2 no instalado. Ejecuta: pip install psycopg2-binary')
    if not _is_configured():
        raise RuntimeError('BD no configurada. Rellena el archivo .env con DB_USER, DB_PASSWORD, DB_HOST, DB_NAME.')
    return psycopg2.connect(**_get_conn_params())


def check_connection() -> dict:
    """
    Verifica la conexión. Devuelve:
      { ok: bool, message: str, host: str|None, db: str|None, latency_ms: float|None }
    """
    if not _is_configured():
        return {
            'ok': False,
            'message': 'Variables de entorno no configuradas. Edita el archivo .env.',
            'host': None, 'db': None, 'latency_ms': None,
        }
    try:
        import time
        t0 = time.time()
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT version();')
            version = cur.fetchone()[0].split(',')[0]
        conn.close()
        latency = round((time.time() - t0) * 1000, 1)
        return {
            'ok': True,
            'message': f'Conexión exitosa — {version}',
            'host': os.getenv('DB_HOST'),
            'db':   os.getenv('DB_NAME'),
            'latency_ms': latency,
        }
    except Exception as e:
        return {
            'ok': False,
            'message': str(e),
            'host': os.getenv('DB_HOST'),
            'db':   os.getenv('DB_NAME'),
            'latency_ms': None,
        }


def ensure_tables():
    """Crea las tablas necesarias si no existen y aplica migraciones seguras."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ── Tabla de usuarios ─────────────────────────────────────────
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    email         VARCHAR(120) UNIQUE NOT NULL,
                    name          VARCHAR(120),
                    password_hash VARCHAR(255) NOT NULL,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    is_active     BOOLEAN DEFAULT TRUE
                );
            ''')

            # ── Tabla de bandeja ──────────────────────────────────────────
            cur.execute('''
                CREATE TABLE IF NOT EXISTS spam_inbox (
                    id          SERIAL PRIMARY KEY,
                    sender      VARCHAR(120),
                    subject     VARCHAR(300),
                    body        TEXT NOT NULL,
                    received_at TIMESTAMPTZ DEFAULT NOW(),
                    is_read     BOOLEAN DEFAULT FALSE
                );
            ''')
            cur.execute('''
                ALTER TABLE spam_inbox
                ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
            ''')

            # ── Tabla de análisis ─────────────────────────────────────────
            cur.execute('''
                CREATE TABLE IF NOT EXISTS spam_analyses (
                    id              SERIAL PRIMARY KEY,
                    inbox_id        INTEGER REFERENCES spam_inbox(id) ON DELETE CASCADE,
                    label           VARCHAR(10) NOT NULL,
                    is_spam         BOOLEAN NOT NULL,
                    confidence      NUMERIC(5,2),
                    spam_prob       NUMERIC(5,2),
                    ham_prob        NUMERIC(5,2),
                    clean_text      TEXT,
                    spam_signals    JSONB,
                    analyzed_at     TIMESTAMPTZ DEFAULT NOW()
                );
            ''')
            cur.execute('''
                ALTER TABLE spam_analyses
                ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
            ''')

            # ── Índices ───────────────────────────────────────────────────
            cur.execute('CREATE INDEX IF NOT EXISTS idx_inbox_received  ON spam_inbox(received_at DESC);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_analyses_inbox  ON spam_analyses(inbox_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_analyses_user   ON spam_analyses(user_id);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_analyses_date   ON spam_analyses(analyzed_at DESC);')

        conn.commit()
    finally:
        conn.close()


# ── Gestión de usuarios ───────────────────────────────────────────────────

def create_user(email: str, name: str, password_hash: str) -> int:
    """Crea un nuevo usuario y devuelve su id. Lanza excepción si el email ya existe."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) RETURNING id',
                (email.lower().strip(), name.strip(), password_hash),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    """Busca un usuario por email. Devuelve dict con id, email, name, password_hash, is_active — o None."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                'SELECT id, email, name, password_hash, is_active FROM users WHERE email = %s',
                (email.lower().strip(),),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_stats(user_id: int) -> dict:
    """Devuelve totales de análisis para el usuario: total, spam, ham, accuracy."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    COUNT(*)                                     AS total,
                    COUNT(*) FILTER (WHERE is_spam = TRUE)      AS spam_count,
                    COUNT(*) FILTER (WHERE is_spam = FALSE)     AS ham_count,
                    ROUND(AVG(confidence)::NUMERIC, 1)          AS avg_confidence
                FROM spam_analyses
                WHERE user_id = %s
            ''', (user_id,))
            total, spam_count, ham_count, avg_conf = cur.fetchone()
        return {
            'total':    int(total or 0),
            'spam':     int(spam_count or 0),
            'ham':      int(ham_count or 0),
            'accuracy': float(avg_conf or 0),
        }
    finally:
        conn.close()


def get_user_recent_analyses(user_id: int, limit: int = 5) -> list:
    """Devuelve los análisis más recientes del usuario."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT label, is_spam, confidence, clean_text, analyzed_at
                FROM spam_analyses
                WHERE user_id = %s
                ORDER BY analyzed_at DESC
                LIMIT %s
            ''', (user_id, limit))
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_all_analyses(user_id: int) -> list:
    """Devuelve todos los análisis del usuario para exportación."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT label, is_spam, confidence, clean_text, analyzed_at
                FROM spam_analyses
                WHERE user_id = %s
                ORDER BY analyzed_at DESC
            ''', (user_id,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_weekly_activity(user_id: int) -> list:
    """Devuelve actividad diaria (últimos 7 días) para el usuario.
    Retorna lista de 7 dicts: {day, total, spam}."""
    from datetime import date, timedelta
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    DATE_TRUNC('day', analyzed_at AT TIME ZONE 'America/Mexico_City')::date AS day,
                    COUNT(*)                                    AS total,
                    COUNT(*) FILTER (WHERE is_spam = TRUE)     AS spam_count
                FROM spam_analyses
                WHERE user_id = %s
                  AND analyzed_at >= NOW() - INTERVAL '7 days'
                GROUP BY 1
                ORDER BY 1
            ''', (user_id,))
            rows = {r[0]: (int(r[1]), int(r[2])) for r in cur.fetchall()}

        # Fill all 7 days even if no data
        day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        result = []
        today = date.today()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            total, spam = rows.get(d, (0, 0))
            result.append({'day': day_names[d.weekday()], 'total': total, 'spam': spam})
        return result
    finally:
        conn.close()


def get_inbox_messages(limit: int = 50) -> list:
    """Lee los últimos mensajes de spam_inbox."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT i.id, i.sender, i.subject, i.body, i.received_at, i.is_read,
                       a.label, a.confidence, a.is_spam
                FROM spam_inbox i
                LEFT JOIN spam_analyses a ON a.inbox_id = i.id
                ORDER BY i.received_at DESC
                LIMIT %s
            ''', (limit,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_analysis(inbox_id: int | None, result: dict, user_id: int | None = None) -> int | None:
    """Guarda el resultado de un análisis en la BD. Devuelve el id."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO spam_analyses
                    (inbox_id, user_id, label, is_spam, confidence, spam_prob, ham_prob,
                     clean_text, spam_signals)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                inbox_id,
                user_id,
                result.get('label'),
                result.get('is_spam'),
                result.get('confidence'),
                result.get('spam_prob'),
                result.get('ham_prob'),
                result.get('clean_text'),
                json.dumps(result.get('spam_signals', [])),
            ))
            analysis_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return analysis_id
    except Exception:
        return None


def seed_demo_messages():
    """Inserta mensajes de ejemplo si la tabla está vacía."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM spam_inbox')
            count = cur.fetchone()[0]
            if count > 0:
                return

            demo = [
                ('Telcel', 'Hoy te damos más', 'Hoy te damos más Gigas GRATIS. Activa tu bono antes del domingo en telcel.com/bono'),
                ('TELCEL', 'Ademas puedes hacer tu recarga', 'Además, puedes hacer tu recarga doble este fin de semana llamando al 800-123-4567'),
                ('TelcelAmzn', 'Amazon: Tu recarga incluye', 'Amazon Prime está incluido en tu plan. Actívalo GRATIS hoy en amzn.to/telcel'),
                ('UNOTV.COM', 'ANTE PRESION EXTERNA', 'ANTE PRESION EXTERNA: El gobierno confirmó nueva política. Lee más en unotv.com'),
                ('ClaroPay', 'Tu paquete de datos', 'Tu paquete de datos está por vencer. Recarga ahora y obtén el doble por tiempo limitado.'),
                ('Google', 'Security alert', 'A new sign-in on Windows. If this was you, you can ignore this message.'),
                ('Banco Azteca', 'Alerta de seguridad', 'URGENTE: Tu cuenta fue bloqueada. Verifica tus datos en bit.ly/azteca-verify AHORA.'),
                ('Papá', 'Para la cena', '¿Ya confirmaste si vas a venir a cenar el domingo? Tu mamá quiere saber cuántos somos.'),
                ('IMSS Digital', 'Apoyo económico', 'Tienes $3,500 pesos de apoyo disponibles. Regístrate GRATIS en imss-apoyos.com hoy.'),
                ('Ana García', 'Reunión del jueves', 'Hola, confirmo asistencia a la reunión del jueves a las 10 AM en sala 3. Saludos.'),
            ]
            cur.executemany(
                'INSERT INTO spam_inbox (sender, subject, body) VALUES (%s, %s, %s)',
                demo
            )
        conn.commit()
    finally:
        conn.close()
