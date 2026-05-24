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
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS spam_inbox (
                    id          SERIAL PRIMARY KEY,
                    sender      VARCHAR(120),
                    subject     VARCHAR(300),
                    body        TEXT NOT NULL,
                    received_at TIMESTAMPTZ DEFAULT NOW(),
                    is_read     BOOLEAN DEFAULT FALSE
                );

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

                CREATE INDEX IF NOT EXISTS idx_inbox_received ON spam_inbox(received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_analyses_inbox ON spam_analyses(inbox_id);
            ''')
        conn.commit()
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


def save_analysis(inbox_id: int | None, result: dict) -> int | None:
    """Guarda el resultado de un análisis en la BD. Devuelve el id."""
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO spam_analyses
                    (inbox_id, label, is_spam, confidence, spam_prob, ham_prob,
                     clean_text, spam_signals)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                inbox_id,
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
