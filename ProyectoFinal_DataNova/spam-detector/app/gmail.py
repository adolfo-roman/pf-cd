"""
gmail.py — Integración con Gmail API (OAuth2 + lectura de bandeja)
Requiere: google-auth-oauthlib, google-api-python-client
Archivo credentials.json descargado de Google Cloud Console.
Token almacenado por usuario: token_<user_id>.json
"""

import base64
from pathlib import Path

SCOPES     = ['https://www.googleapis.com/auth/gmail.readonly']
CREDS_PATH = Path(__file__).resolve().parents[1] / 'credentials.json'
_TOKENS_DIR = Path(__file__).resolve().parents[1]


def _token_path(user_id=None) -> Path:
    """Devuelve la ruta del token para el usuario dado (o token global si no hay user_id)."""
    if user_id:
        return _TOKENS_DIR / f'token_{user_id}.json'
    return _TOKENS_DIR / 'token.json'


def has_credentials() -> bool:
    return CREDS_PATH.exists()


def get_redirect_uri() -> str:
    """Lee el primer redirect_uri registrado en credentials.json."""
    import json
    data = json.loads(CREDS_PATH.read_text())
    client = data.get('web') or data.get('installed') or {}
    uris = client.get('redirect_uris', [])
    if not uris:
        raise ValueError('No redirect_uris en credentials.json')
    return uris[0]


def _load_creds(user_id=None):
    from google.oauth2.credentials import Credentials
    tp = _token_path(user_id)
    if tp.exists():
        return Credentials.from_authorized_user_file(str(tp), SCOPES)
    return None


def _refresh_if_needed(creds, user_id=None):
    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        _token_path(user_id).write_text(creds.to_json())
    return creds


def is_connected(user_id=None) -> bool:
    try:
        creds = _load_creds(user_id)
        if not creds:
            return False
        creds = _refresh_if_needed(creds, user_id)
        return creds.valid
    except Exception:
        return False


def get_auth_url(redirect_uri: str) -> str:
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        str(CREDS_PATH), scopes=SCOPES, redirect_uri=redirect_uri
    )
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    return auth_url


def exchange_code(code: str, redirect_uri: str, user_id=None) -> None:
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        str(CREDS_PATH), scopes=SCOPES, redirect_uri=redirect_uri
    )
    flow.fetch_token(code=code)
    _token_path(user_id).write_text(flow.credentials.to_json())


def disconnect(user_id=None) -> None:
    tp = _token_path(user_id)
    if tp.exists():
        tp.unlink()


def get_messages(max_results: int = 25, user_id=None) -> list:
    from googleapiclient.discovery import build

    creds = _load_creds(user_id)
    if not creds:
        raise RuntimeError('Gmail no conectado. Autoriza primero.')
    creds = _refresh_if_needed(creds, user_id)
    if not creds.valid:
        raise RuntimeError('Token de Gmail inválido. Reconecta tu cuenta.')

    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    result = service.users().messages().list(
        userId='me', maxResults=max_results, labelIds=['INBOX']
    ).execute()

    messages = []
    for item in result.get('messages', []):
        try:
            raw = service.users().messages().get(
                userId='me', id=item['id'], format='full'
            ).execute()
            messages.append(_parse_message(raw))
        except Exception:
            continue

    return messages


def _parse_message(msg: dict) -> dict:
    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
    body    = _extract_body(msg['payload']) or msg.get('snippet', '')

    return {
        'id':          msg['id'],           # string — Gmail message ID
        'thread_id':   msg.get('threadId'),
        'sender':      headers.get('From', 'Desconocido'),
        'subject':     headers.get('Subject', '(sin asunto)'),
        'body':        body,
        'received_at': headers.get('Date', ''),
        'is_read':     'UNREAD' not in msg.get('labelIds', []),
        'label':       None,
        'confidence':  None,
        'is_spam':     None,
        'source':      'gmail',
    }


def _extract_body(payload: dict) -> str:
    mime = payload.get('mimeType', '')

    # multipart: buscar text/plain primero
    if mime.startswith('multipart'):
        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/plain':
                return _decode_data(part['body'].get('data', ''))
        # fallback: primer part recursivo
        parts = payload.get('parts', [])
        if parts:
            return _extract_body(parts[0])

    # single part text/plain
    if mime == 'text/plain':
        return _decode_data(payload.get('body', {}).get('data', ''))

    return ''


def _decode_data(data: str) -> str:
    if not data:
        return ''
    padding = len(data) % 4
    if padding:
        data += '=' * (4 - padding)
    return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
