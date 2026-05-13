import streamlit as st
import onnxruntime as rt
import numpy as np
import pandas as pd
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
import string
import psycopg2

# Credenciales de base de datos extraídas del ticket
DB_USER = "aegis"
DB_PASS = "LnaXQfQpN2rXHwYl"

st.set_page_config(page_title="Spam ML Dashboard", layout="wide")
st.title("🛡️ Anti-Spam Filter (Local ML Inference)")
st.markdown("The ONNX model is running directly on your local machine.")

@st.cache_resource
def setup_nlp():
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    return PorterStemmer(), set(stopwords.words('english'))

ps, stop_words_english = setup_nlp()

def clean_input(text):
    text = text.lower()
    text = nltk.word_tokenize(text)
    y = [i for i in text if i.isalnum()]
    y = [i for i in y if i not in stop_words_english and i not in string.punctuation]
    y = [ps.stem(i) for i in y]
    return " ".join(y)

@st.cache_resource
def load_model():
    return rt.InferenceSession("modelo_produccion.onnx")

try:
    sess = load_model()
    model_loaded = True
except Exception as e:
    st.error(f"Error loading ONNX: {e}")
    model_loaded = False

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("SMS/Email Evaluator")
    user_input = st.text_area("Paste the message here:", height=150)

    if st.button("Evaluate"):
        if user_input and model_loaded:
            # Extracción de características estáticas
            m_len = np.float32(len(str(user_input)))
            num_up = np.float32(sum(1 for c in str(user_input) if c.isupper()))
            num_dig = np.float32(sum(1 for c in str(user_input) if c.isdigit()))

            cleaned_text = clean_input(user_input)

            # Formateo de las variables como lo espera el modelo ONNX local
            inputs = {
                'clean_text': np.array([[cleaned_text]]),
                'message_length': np.array([[m_len]], dtype=np.float32),
                'num_uppercase': np.array([[num_up]], dtype=np.float32),
                'num_digits': np.array([[num_dig]], dtype=np.float32)
            }

            label_name = sess.get_outputs()[0].name
            pred = sess.run([label_name], inputs)[0]

            st.markdown("---")
            if pred[0] == 1:
                st.error("🚨 **SPAM DETECTED**")
            else:
                st.success("✅ **LEGITIMATE MESSAGE (HAM)**")

            st.caption(f"Length: {int(m_len)} | Uppercase: {int(num_up)} | Digits: {int(num_dig)}")
        else:
            st.warning("Please enter a valid text.")

with col2:
    st.subheader("Evaluation Logs")
    try:
        with open("metricas_entrenamiento.txt", "r") as f:
            st.code(f.read(), language="text")
    except:
        st.write("Logs not available.")
