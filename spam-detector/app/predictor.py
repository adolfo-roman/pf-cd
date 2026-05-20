"""
predictor.py — Módulo de inferencia bilingüe (inglés + español)
Usa el mismo preprocesamiento que retrain_spanish.py para coherencia total.
"""

import re
import joblib
import pandas as pd
from pathlib import Path

# ── Stopwords EN + ES ─────────────────────────────────────────────────────
STOPWORDS = {
    # inglés
    'i','me','my','we','our','you','your','he','him','his','she','her','it',
    'its','they','them','their','what','which','who','this','that','these',
    'those','am','is','are','was','were','be','been','have','has','had',
    'do','does','did','a','an','the','and','but','if','or','as','at','by',
    'for','with','about','to','from','in','out','on','off','over','not',
    'no','so','can','will','just','now','s','t','ll','re','ve','d','m',
    # español
    'de','la','que','el','en','y','a','los','del','se','las','por','un',
    'para','con','no','una','su','al','es','lo','como','mas','pero','sus',
    'le','ya','o','si','porque','esta','entre','cuando','muy','sin','sobre',
    'ser','tiene','todo','hay','fue','era','son','dos','mi','cual','bien',
    'ni','tu','te','yo','he','ella','ellos','nos','les','algo','alguien',
    'nadie','nada','cada','tanto','tan','donde','quien','antes','despues',
    'mientras','durante','entonces','tambien','ademas','aunque','incluso',
    'sino','pues','luego','asi','ahi','aqui','alla','alli','este','ese',
    'eso','han','ser','estar','haber','tener','hacer','poder',
}

_SUFFIXES = [
    'ando','iendo','ción','cion','mente','ados','idas','idos',
    'ing','tion','ed','er','ly',
]

def _stem(word: str) -> str:
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) > 2:
            return word[:-len(suf)]
    return word

def preprocess(text: str) -> str:
    """Preprocesa texto bilingüe ES/EN: igual al pipeline de entrenamiento."""
    text = re.sub(r'https?\S+', ' ', str(text))
    # Permite letras con tilde/ñ además del ASCII
    text = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]', ' ', text)
    text = text.lower()
    tokens = [_stem(w) for w in text.split()
              if w not in STOPWORDS and len(w) > 1]
    return ' '.join(tokens)

def _build_df(raw_text: str) -> pd.DataFrame:
    n_chars = len(raw_text)
    n_upper = sum(1 for c in raw_text if c.isupper())
    return pd.DataFrame({
        'texto_limpio':    [preprocess(raw_text)],
        'num_caracteres':  [float(n_chars)],
        'num_mayusculas':  [float(n_upper)],
        'num_digitos':     [float(sum(1 for c in raw_text if c.isdigit()))],
        'ratio_mayusculas':[float(n_upper) / (n_chars + 1)],
    })

# ── Carga lazy del modelo ─────────────────────────────────────────────────
_MODEL      = None
_MODEL_PATH = Path(__file__).resolve().parents[1] / 'ml_pipeline' / 'models' / 'modelo_final.joblib'

def _get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(_MODEL_PATH)
    return _MODEL

# ── API pública ───────────────────────────────────────────────────────────
def predict_message(text: str) -> dict:
    """
    Clasifica un SMS en spam o ham (inglés y español).

    Retorna:
    {
        label:      'spam' | 'ham',
        is_spam:    bool,
        confidence: 0–100 (prob de la clase predicha),
        spam_prob:  0–100,
        ham_prob:   0–100,
        clean_text: str,
        stats: { num_chars, num_uppercase, num_digits }
    }
    """
    model = _get_model()
    df    = _build_df(text)

    pred      = int(model.predict(df)[0])          # 0=ham, 1=spam
    proba     = model.predict_proba(df)[0]         # [p_ham, p_spam]
    ham_prob  = float(proba[0])
    spam_prob = float(proba[1])
    is_spam   = pred == 1
    confidence = spam_prob if is_spam else ham_prob

    # ── Señales detectadas para explicación en UI ─────────────────────────
    spam_signals = _detect_signals(text)

    return {
        'label':      'spam' if is_spam else 'ham',
        'is_spam':    is_spam,
        'confidence': round(confidence * 100, 1),
        'spam_prob':  round(spam_prob  * 100, 1),
        'ham_prob':   round(ham_prob   * 100, 1),
        'clean_text': preprocess(text),
        'spam_signals': spam_signals,
        'stats': {
            'num_chars':       len(text),
            'num_uppercase':   sum(1 for c in text if c.isupper()),
            'num_digits':      sum(1 for c in text if c.isdigit()),
            'ratio_uppercase': round(sum(1 for c in text if c.isupper()) / (len(text)+1) * 100, 1),
        },
    }

# ── Detección de señales explicables ──────────────────────────────────────
_SPAM_KEYWORDS = {
    # Premios / ganar
    'win','won','winner','winning','prize','reward','cash','gift','free',
    'claim','awarded','selected','congratulations','lucky',
    'ganaste','ganó','ganador','premio','regalo','gratis','reclama','seleccionado',
    'felicidades','suerte','recompensa',
    # Urgencia
    'urgent','urgente','act now','actúa','immediately','inmediatamente',
    'expires','vence','limited','limitado','hurry','apúrate','tonight','midnight',
    'final notice','aviso final','last chance','última oportunidad',
    # Dinero
    'money','cash','pounds','pesos','dollars','£','$','€',
    'dinero','efectivo',
    # Acción
    'click','clic','call','llama','reply','responde','verify','verifica',
    'confirm','confirma','subscribe','suscríbete',
    # Phishing
    'account','cuenta','password','contraseña','suspended','suspendida',
    'verify','verificar','security','seguridad','blocked','bloqueada',
}

def _detect_signals(text: str) -> list:
    """Devuelve lista de señales de spam detectadas en el texto."""
    signals = []
    text_lower = text.lower()
    words = set(re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]', ' ', text_lower).split())

    # Palabras clave
    found_kw = [w for w in words if w in _SPAM_KEYWORDS]
    if found_kw:
        sample = ', '.join(sorted(found_kw)[:4])
        signals.append({'type': 'keywords', 'label': 'Palabras clave spam', 'detail': sample})

    # Mayúsculas excesivas
    n_chars = len(text)
    n_upper = sum(1 for c in text if c.isupper())
    ratio   = n_upper / (n_chars + 1)
    if ratio > 0.3:
        signals.append({'type': 'uppercase', 'label': 'Mayúsculas excesivas',
                        'detail': f'{ratio*100:.0f}% del texto en mayúsculas'})

    # Números de teléfono / códigos
    if re.search(r'\d{6,}', text):
        signals.append({'type': 'phone', 'label': 'Número telefónico o código',
                        'detail': 'Contiene secuencia numérica larga'})

    # URLs sospechosas
    if re.search(r'(bit\.ly|tinyurl|goo\.gl|cutt\.ly|rb\.gy|http)', text_lower):
        signals.append({'type': 'url', 'label': 'URL acortada o sospechosa',
                        'detail': 'Contiene enlace potencialmente peligroso'})

    # Símbolos monetarios
    if re.search(r'[\$£€]|\d+[,\s]?\d+\s*(pesos|pounds|dollars|usd|mxn)', text_lower):
        signals.append({'type': 'money', 'label': 'Mención de dinero',
                        'detail': 'Contiene símbolo o monto monetario'})

    # Signos de exclamación múltiples
    if text.count('!') >= 2:
        signals.append({'type': 'exclamation', 'label': 'Urgencia tipográfica',
                        'detail': f'{text.count("!")} signos de exclamación'})

    return signals
