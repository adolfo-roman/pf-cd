"""
retrain_bilingual.py
Genera ~800 ejemplos bilingües cubriendo TODOS los patrones de spam:
  - Con teléfono/URL (ya funcionaba)
  - Solo texto urgente / premios  ← GAP PRINCIPAL
  - Phishing suave
  - Spam en español natural
Re-entrena con bigrams + feature extra de mayúsculas ratio.
"""

import re, random, joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, precision_score, recall_score, f1_score
from sklearn.base import BaseEstimator, TransformerMixin

BASE   = Path(__file__).parent
DATA   = BASE / "ml_pipeline" / "data" / "spam.csv"
MODELS = BASE / "ml_pipeline" / "models"
MODELS.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42
random.seed(RANDOM_STATE)

# ── Stopwords EN+ES ────────────────────────────────────────────────────────
STOPWORDS = {
    'i','me','my','we','our','you','your','he','him','his','she','her','it',
    'its','they','them','their','what','which','who','this','that','these',
    'those','am','is','are','was','were','be','been','have','has','had',
    'do','does','did','a','an','the','and','but','if','or','as','at','by',
    'for','with','about','to','from','in','out','on','off','over','not',
    'no','so','can','will','just','now','s','t','ll','re','ve','d','m',
    'de','la','que','el','en','y','a','los','del','se','las','por','un',
    'para','con','no','una','su','al','es','lo','como','mas','pero','sus',
    'le','ya','o','si','porque','esta','entre','cuando','muy','sin','sobre',
    'ser','tiene','todo','hay','fue','era','son','dos','mi','cual','bien',
    'ni','tu','te','yo','he','ella','ellos','nos','les','algo','alguien',
    'nadie','nada','cada','tanto','tan','donde','quien','antes','despues',
    'mientras','durante','entonces','tambien','ademas','aunque','incluso',
    'sino','pues','luego','asi','ahi','aqui','alla','alli','este','ese',
    'eso','han','estar','haber','tener','hacer','poder',
}

def stem(word):
    for suf in ['ando','iendo','cion','mente','ados','idas','idos','ing','tion','ed','er','ly']:
        if word.endswith(suf) and len(word)-len(suf) > 2:
            return word[:-len(suf)]
    return word

def preprocess(text):
    text = re.sub(r'https?\S+', ' ', str(text))
    text = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]', ' ', text)
    text = text.lower()
    return ' '.join(stem(w) for w in text.split() if w not in STOPWORDS and len(w)>1)

# ── Datos sintéticos ────────────────────────────────────────────────────────
# SPAM EN — patrones sin teléfono (el gap principal)
SPAM_EN_TEXT = [
    # Solo texto urgente / premios
    "YOU WIN A CAR! Claim your prize today before it expires.",
    "YOU HAVE WON a free vacation! Respond now to claim.",
    "CONGRATULATIONS! You are our lucky winner. Claim now.",
    "FREE GIFT waiting for you. Collect your reward today!",
    "You are SELECTED for our exclusive offer. Reply YES now.",
    "WIN WIN WIN! You qualify for a special cash reward.",
    "URGENT: You have unclaimed rewards. Act immediately.",
    "FINAL NOTICE: Claim your prize or it will be reassigned.",
    "You have been chosen! Exclusive member benefit available.",
    "LIMITED TIME: Free entry to win luxury vacation package.",
    "Claim your FREE iPhone now. Limited stock available today.",
    "You qualify for a special promotion. Don't miss this chance!",
    "SPECIAL OFFER for selected customers only. Reply to claim.",
    "YOU ARE THE WINNER of our monthly draw. Respond immediately.",
    "FREE money waiting. You have been pre-approved for a cash gift.",
    "Congratulations! Your number won the weekly prize draw.",
    "ACT NOW and claim your complimentary gift. Offer expires soon.",
    "You have won exclusive access to premium rewards. Reply YES.",
    "ALERT: Unclaimed prize in your name. Contact us now.",
    "You are guaranteed a prize. Claim before midnight tonight.",
    # Con URLs genéricas
    "Click here to claim your FREE prize www.claim-now.info",
    "Get your reward at bit.ly/free-gift — expires today",
    "Visit our site NOW to collect your exclusive bonus offer.",
    "You won! See details at our website before offer expires.",
    # Phishing suave
    "Your account needs immediate verification. Confirm now.",
    "Security alert: Unusual activity detected. Verify identity.",
    "Your password expires today. Update immediately to continue.",
    "IMPORTANT: Your subscription will be cancelled. Renew now.",
    "Action required: Confirm your details to avoid suspension.",
    "WARNING: Your account will be closed. Respond immediately.",
    # Adulto / enganche
    "Hot singles in your area want to meet you tonight. Reply.",
    "Someone likes you! Find out who. Click to reveal your match.",
    "You have 3 secret admirers. Discover them now for free.",
    "Meet sexy locals tonight. Free registration. Join now!",
]

# SPAM EN variaciones con mayúsculas (importante para el feature de ratio)
SPAM_EN_CAPS = [
    "YOU WIN A {prize}! CLAIM NOW BEFORE IT EXPIRES!",
    "FREE {prize}! YOU HAVE BEEN SELECTED! ACT NOW!",
    "URGENT! WIN {prize} TODAY! REPLY YES TO CLAIM!",
    "WINNER! YOU WON {prize}! CLAIM YOUR REWARD NOW!",
    "CONGRATULATIONS! FREE {prize}! LIMITED TIME ONLY!",
    "YOU ARE THE LUCKY WINNER OF A {prize}! CLAIM TODAY!",
    "CLAIM YOUR FREE {prize} BEFORE MIDNIGHT TONIGHT!",
    "SELECTED! FREE {prize} FOR YOU! RESPOND IMMEDIATELY!",
]

# SPAM ES — patrones sin teléfono
SPAM_ES_TEXT = [
    "¡GANASTE UN AUTO! Reclama tu premio antes de que expire.",
    "¡FELICIDADES! Eres el ganador seleccionado. Responde YA.",
    "REGALO GRATIS esperando por ti. Recoge tu recompensa hoy.",
    "¡URGENTE! Tienes premios sin reclamar. Actúa de inmediato.",
    "Fuiste SELECCIONADO para oferta exclusiva. Responde AHORA.",
    "¡GANA GANA GANA! Calificas para recompensa especial en efectivo.",
    "AVISO FINAL: Reclama tu premio o será reasignado mañana.",
    "¡Has sido elegido! Beneficio exclusivo disponible hoy.",
    "TIEMPO LIMITADO: Entrada gratis para ganar paquete de viaje.",
    "Reclama tu iPhone GRATIS ahora. Stock limitado disponible.",
    "Calificas para promoción especial. ¡No pierdas esta oportunidad!",
    "OFERTA ESPECIAL solo para clientes seleccionados. Responde para reclamar.",
    "¡ERES EL GANADOR del sorteo mensual! Responde de inmediato.",
    "Dinero GRATIS esperándote. Fuiste pre-aprobado para regalo en efectivo.",
    "¡Felicidades! Tu número ganó el sorteo semanal de premios.",
    "ACTÚA AHORA y reclama tu regalo gratuito. Oferta vence pronto.",
    "Ganaste acceso exclusivo a recompensas premium. Responde SÍ.",
    "ALERTA: Premio sin reclamar a tu nombre. Contáctanos ya.",
    "Tienes un premio garantizado. Reclama antes de la medianoche.",
    "¡GANA UN CARRO! Solo responde este mensaje para participar.",
    "Haz CLIC AQUÍ para reclamar tu premio GRATIS hoy mismo.",
    "Visita nuestro sitio AHORA para recoger tu bono exclusivo.",
    "¡Ganaste! Ver detalles en nuestro sitio antes que expire.",
    # Phishing ES
    "Tu cuenta necesita verificación inmediata. Confirma ahora.",
    "ALERTA de seguridad: Actividad inusual detectada. Verifica.",
    "Tu contraseña vence hoy. Actualiza de inmediato para continuar.",
    "IMPORTANTE: Tu suscripción será cancelada. Renueva ya.",
    "Acción requerida: Confirma tus datos para evitar suspensión.",
    "ADVERTENCIA: Tu cuenta será cerrada. Responde de inmediato.",
    # Con montos sin teléfono
    "¡Ganaste $50,000 pesos! Reclama tu premio respondiendo SÍ.",
    "Te esperan $10,000 pesos de recompensa. Responde para cobrar.",
    "Premio de $25,000 pesos a tu nombre. Reclama antes del viernes.",
    "Bono de $5,000 pesos disponible para ti. Responde COBRAR.",
]

SPAM_ES_CAPS = [
    "¡GANASTE UN {premio}! ¡RECLAMA AHORA ANTES DE QUE EXPIRE!",
    "¡{premio} GRATIS! ¡FUISTE SELECCIONADO! ¡ACTÚA YA!",
    "¡URGENTE! ¡GANA {premio} HOY! ¡RESPONDE SÍ PARA RECLAMAR!",
    "¡GANADOR! ¡GANASTE {premio}! ¡RECLAMA TU RECOMPENSA AHORA!",
    "¡FELICIDADES! ¡{premio} GRATIS! ¡SOLO POR TIEMPO LIMITADO!",
    "¡ERES EL GANADOR AFORTUNADO DE {premio}! ¡RECLAMA HOY!",
]

# SPAM con teléfono/URL (refuerzo)
SPAM_CON_TEL = [
    "¡FELICIDADES! Ganaste {premio}. Llama AHORA al {tel} para reclamar.",
    "URGENTE: Tu cuenta {banco} será SUSPENDIDA. Verifica en {url}",
    "Ganaste {monto} pesos. Envía tu CURP al {tel} para cobrar HOY.",
    "GRATIS: Descarga {app} y gana {monto} pesos. Regístrate en {url}",
    "Tu paquete fue retenido. Paga {monto} pesos en {url} para liberarlo.",
    "SAT: Devolución de {monto} pesos pendiente. Valida en {url}",
    "Préstamo de {monto} sin buró. Depósito en 10 min. Solicita al {tel}.",
    "FREE entry in 2 a wkly comp to win FA Cup tkts. Text FA to {shortcode}",
    "WINNER!! You have been selected for a £{amount} prize. Call {tel}",
    "FREE MSG: You have won a £{amount} prize. Claim at {url}",
    "Congratulations ur awarded {amount} of CD vouchers. Text YES to {shortcode}",
    "Win a £{amount} cash prize. Text WIN to {shortcode} now.",
]

# HAM EN natural
HAM_EN = [
    "Hey, are you free tonight for dinner?",
    "Meeting moved to 3pm tomorrow, can you make it?",
    "Just landed, picking up bags now. See you in 30.",
    "Thanks for your help yesterday, really appreciated it.",
    "Happy birthday! Hope you have an amazing day today.",
    "Can you send me the report before the meeting please?",
    "Running 10 min late, traffic is terrible. Sorry!",
    "Did you see the game last night? What a match!",
    "Reminder: dentist appointment tomorrow at 2pm.",
    "Groceries picked up. Do you need anything else?",
    "The package arrived, everything looks good. Thanks!",
    "Let me know when you're free and we can catch up.",
    "Great work on the presentation today, client loved it.",
    "Mom said dinner is at 7. Don't forget to bring dessert.",
    "Your order has been shipped. Delivery in 2-3 business days.",
    "OK sounds good, see you there at 6.",
    "I'll be home by 8, can you start dinner?",
    "Call me when you get a chance, nothing urgent.",
    "The wifi password is printed on the router.",
    "Good morning! Hope you have a great day.",
    "Confirmed for Saturday, looking forward to it!",
    "Sorry I missed your call, in a meeting. Call later?",
    "The doctor said everything looks normal, no worries.",
    "Can we reschedule to next week? Something came up.",
    "Just finished work, on my way home now.",
]

# HAM ES natural
HAM_ES = [
    "Hola, ¿puedes hablar en un momento? Quiero platicarte algo.",
    "Ya llegué, estoy esperando en la entrada del metro.",
    "Recuerda que mañana es la reunión a las 10 AM.",
    "¿Me puedes traer leche del súper cuando regreses?",
    "El reporte ya está listo, lo mandé al correo hace un rato.",
    "Buen día equipo, les comparto el avance de la semana.",
    "¿A qué hora sale tu vuelo? Para ir a recogerte.",
    "Feliz cumpleaños! Que la pases muy bien hoy.",
    "Ya pagué la renta, el comprobante está en WhatsApp.",
    "La junta se movió para las 4:30 PM en sala 3.",
    "¿Qué van a pedir de comer? Yo quiero tacos.",
    "Llego como en 15 minutos, ya voy saliendo del trabajo.",
    "Buen trabajo en la presentación, el cliente quedó contento.",
    "¿Ya viste el partido anoche? Estuvo increíble.",
    "Mamá, ya estoy en casa. Comí bien, no te preocupes.",
    "El doctor dice que todo está bien, solo tomar medicamento.",
    "Confirmo nuestra cita del viernes a las 3 PM.",
    "Oye, ¿tienes el número del plomero? Se descompuso el baño.",
    "Gracias por tu ayuda ayer, de verdad me salvaste.",
    "La entrega llegó bien. Muchas gracias por el envío.",
    "¿Puedes revisar el documento antes de que lo mande?",
    "Ya subí los archivos a la carpeta compartida.",
    "Hoy no puedo ir al gym, quedé con mis papás.",
    "Acabo de llegar al hotel, todo bien. Mañana te cuento.",
    "Buenas tardes, te mando los datos por correo ahora.",
    "Nos vemos el martes entonces, que tengas buen fin.",
    "Ya está listo tu pedido, puedes pasar a recogerlo.",
    "Se me olvidó avisarte, mañana no hay clase.",
    "El jefe dijo que el viernes es día libre para todos.",
    "¿Cómo va tu proyecto? Cualquier cosa me dices.",
]

# Llenadores
PREMIOS  = ["un auto","un iPhone 15","$50,000 pesos","un viaje a Cancún","una Smart TV"]
BANCOS   = ["BBVA","Banamex","Santander","Banorte","HSBC"]
TELS     = ["55-1234-5678","800-123-4567","01800-555-0000","33-1111-2222"]
URLS     = ["bit.ly/cl4im","goo.gl/prz24","tinyurl.com/win","cutt.ly/premio"]
MONTOS   = ["5,000","10,500","2,300","15,000","8,900"]
APPS     = ["CashApp MX","BancoPlus","PremioApp"]
SHORTCODES = ["87575","85233","81010","69698","84484"]
AMOUNTS  = ["900","1000","5000","500","2000"]
PRIZES_EN = ["a car","a vacation","an iPhone","$10,000 cash","a luxury gift"]

def fill(t):
    return (t.replace("{premio}", random.choice(PREMIOS))
             .replace("{banco}", random.choice(BANCOS))
             .replace("{tel}", random.choice(TELS))
             .replace("{url}", random.choice(URLS))
             .replace("{monto}", random.choice(MONTOS))
             .replace("{app}", random.choice(APPS))
             .replace("{shortcode}", random.choice(SHORTCODES))
             .replace("{amount}", random.choice(AMOUNTS))
             .replace("{prize}", random.choice(PRIZES_EN)))

def build_dataset():
    rows = []

    # Spam EN sin teléfono (el gap principal) — 3x repetición con variaciones
    for _ in range(3):
        for t in SPAM_EN_TEXT:
            rows.append(("spam", t))
        for t in SPAM_EN_CAPS:
            rows.append(("spam", fill(t)))

    # Spam ES sin teléfono
    for _ in range(3):
        for t in SPAM_ES_TEXT:
            rows.append(("spam", t))
        for t in SPAM_ES_CAPS:
            rows.append(("spam", fill(t)))

    # Spam con tel/URL (refuerzo)
    for _ in range(4):
        for t in SPAM_CON_TEL:
            rows.append(("spam", fill(t)))

    # Ham
    for _ in range(4):
        for t in HAM_EN:
            rows.append(("ham", t))
        for t in HAM_ES:
            rows.append(("ham", t))

    df = pd.DataFrame(rows, columns=["v1","v2"])
    return df.drop_duplicates(subset="v2")

# ── Main ────────────────────────────────────────────────────────────────────
print("📂 Cargando dataset original...")
df_orig = pd.read_csv(DATA, encoding='latin-1')[['v1','v2']].dropna()
df_orig.columns = ['v1','v2']
print(f"   Original: {len(df_orig)} | spam={df_orig[df_orig.v1=='spam'].shape[0]} ham={df_orig[df_orig.v1=='ham'].shape[0]}")

print("🧪 Generando datos sintéticos bilingües...")
df_synth = build_dataset()
print(f"   Sintéticos: {len(df_synth)} | spam={df_synth[df_synth.v1=='spam'].shape[0]} ham={df_synth[df_synth.v1=='ham'].shape[0]}")

df = pd.concat([df_orig, df_synth], ignore_index=True).drop_duplicates(subset='v2').sample(frac=1, random_state=RANDOM_STATE)
print(f"   Dataset total: {len(df)} | spam={df[df.v1=='spam'].shape[0]} ham={df[df.v1=='ham'].shape[0]}")

print("⚙️  Feature engineering...")
df['num_caracteres']    = df['v2'].apply(len).astype(float)
df['num_mayusculas']    = df['v2'].apply(lambda x: sum(1 for c in str(x) if c.isupper())).astype(float)
df['num_digitos']       = df['v2'].apply(lambda x: sum(1 for c in str(x) if c.isdigit())).astype(float)
# NUEVO: ratio de mayúsculas — muy discriminativo para "YOU WIN A CAR"
df['ratio_mayusculas']  = (df['num_mayusculas'] / (df['num_caracteres'] + 1)).astype(float)
df['texto_limpio']      = df['v2'].apply(preprocess)
df['label_num']         = df['v1'].map({'ham':0,'spam':1})

X = df[['texto_limpio','num_caracteres','num_mayusculas','num_digitos','ratio_mayusculas']]
y = df['label_num']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
print(f"   Train: {len(X_train)}  Test: {len(X_test)}")

print("🤖 Entrenando SVM con bigrams + ratio_mayusculas...")
preprocessor = ColumnTransformer([
    ('texto', TfidfVectorizer(
        max_features=5000,
        ngram_range=(1,2),      # bigrams capturan "you win", "free gift", etc.
        sublinear_tf=True,      # reduce dominancia de palabras frecuentes
    ), 'texto_limpio'),
    ('numeros', MinMaxScaler(),
     ['num_caracteres','num_mayusculas','num_digitos','ratio_mayusculas']),
])

pipeline = Pipeline([
    ('preprocesamiento', preprocessor),
    ('clasificador', CalibratedClassifierCV(
        LinearSVC(class_weight='balanced', C=1.0, max_iter=3000, random_state=RANDOM_STATE),
        cv=3
    )),
])

pipeline.fit(X_train, y_train)

y_pred = pipeline.predict(X_test)
print("\n📊 Métricas en test set:")
print(classification_report(y_test, y_pred, target_names=['ham','spam']))

joblib.dump(pipeline, MODELS / 'modelo_final.joblib')
print(f"✅ Modelo guardado.")

# ── Prueba final ────────────────────────────────────────────────────────────
def pred(text):
    row = pd.DataFrame({
        'texto_limpio':   [preprocess(text)],
        'num_caracteres': [float(len(text))],
        'num_mayusculas': [float(sum(1 for c in text if c.isupper()))],
        'num_digitos':    [float(sum(1 for c in text if c.isdigit()))],
        'ratio_mayusculas': [float(sum(1 for c in text if c.isupper())) / (len(text)+1)],
    })
    p = pipeline.predict(row)[0]
    pr = pipeline.predict_proba(row)[0]
    return f"{'SPAM' if p==1 else 'HAM ':4} {max(pr)*100:5.1f}%"

print("\n🧪 Prueba de casos problemáticos:")
casos = [
    "YOU WIN A CAR",
    "YOU HAVE WON A FREE VACATION",
    "Congratulations you won a prize",
    "FREE GIFT claim now",
    "URGENT claim your reward today",
    "Win a car today",
    "You are selected for exclusive offer",
    "¡GANASTE UN AUTO! Reclama tu premio",
    "¡FELICIDADES! Eres el ganador seleccionado",
    "Hola, ya llegué al metro, espérame 5 minutos",
    "Confirmo asistencia a la reunión del viernes",
    "FREE PRIZE WIN £1000 call 08002986030 NOW",
    "Hey are you free tonight for dinner?",
]
for t in casos:
    print(f"  {pred(t)} | {t}")

print("\n🎉 Listo.")
