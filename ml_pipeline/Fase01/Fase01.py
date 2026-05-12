import pandas as pd
import numpy as np
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)

def ejecutar_fase_1(ruta_input="spam.csv", ruta_output="spam_limpio.csv"):
    print("Iniciando Fase 1: Limpieza y Feature Engineering...")

    df = pd.read_csv(ruta_input, encoding='latin-1')

    # Limpieza estructural
    columnas_basura = ['Unnamed: 2', 'Unnamed: 3', 'Unnamed: 4']
    df = df.drop(columns=[col for col in columnas_basura if col in df.columns])
    df = df.rename(columns={'v1': 'label', 'v2': 'texto_original'})
    df = df.drop_duplicates()

    # Ingeniería de Características - Características numéricas
    df['num_caracteres'] = df['texto_original'].apply(len).astype(np.float32)
    df['num_mayusculas'] = df['texto_original'].apply(lambda x: sum(1 for c in str(x) if c.isupper())).astype(np.float32)
    df['num_digitos'] = df['texto_original'].apply(lambda x: sum(1 for c in str(x) if c.isdigit())).astype(np.float32)

    # Procesamiento de Lenguaje Natural (NLP)
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()


    # Convertir a minúsculas y tokenizar, eliminar stopwords y lematizar
    def limpiar_texto(texto):
        texto = re.sub(r'http\S+', '', str(texto))
        texto = re.sub(r'[^a-zA-Z]', ' ', texto)
        tokens = texto.lower().split()
        tokens_limpios = [lemmatizer.lemmatize(word) for word in tokens if word not in stop_words]
        return ' '.join(tokens_limpios)

    df['texto_limpio'] = df['texto_original'].apply(limpiar_texto)
    df['label_num'] = df['label'].map({'ham': 0, 'spam': 1})
    df_final = df[['label_num', 'texto_limpio', 'num_caracteres', 'num_mayusculas', 'num_digitos']]

    df_final.to_csv(ruta_output, index=False)
    print(f"Fase 1 completada. Archivo generado: {ruta_output}")

    return df_final