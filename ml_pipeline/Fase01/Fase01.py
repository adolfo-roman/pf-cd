import pandas as pd
import numpy as np
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sqlalchemy import create_engine

nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)

def ejecutar_fase_1_db():
    print("Iniciando Fase 1: Extracción, Limpieza y Feature Engineering desde la BD...")

    # Conexión a la base de datos en DigitalOcean
    db_url = "postgresql://doadmin:*************@db-postgresql-nyc3-02715-do-user-28207668-0.h.db.ondigitalocean.com:25060/defaultdb?sslmode=require"
    engine = create_engine(db_url)

    # Extracción (E) - Leemos de spam_raw y renombramos directamente en SQL por eficiencia
    query = "SELECT v1 AS label, v2 AS texto_original FROM spam_raw"
    df = pd.read_sql(query, engine)
    
    df = df.drop_duplicates()

    # Transformación (T) - Ingeniería de Características
    print("Calculando metadatos (longitud, mayúsculas, dígitos)...")
    df['num_caracteres'] = df['texto_original'].apply(len).astype(np.float32)
    df['num_mayusculas'] = df['texto_original'].apply(lambda x: sum(1 for c in str(x) if c.isupper())).astype(np.float32)
    df['num_digitos'] = df['texto_original'].apply(lambda x: sum(1 for c in str(x) if c.isdigit())).astype(np.float32)

    # Procesamiento de Lenguaje Natural (NLP)
    print("Aplicando limpieza NLP...")
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()

    def limpiar_texto(texto):
        texto = re.sub(r'http\S+', '', str(texto))
        texto = re.sub(r'[^a-zA-Z]', ' ', texto)
        tokens = texto.lower().split()
        tokens_limpios = [lemmatizer.lemmatize(word) for word in tokens if word not in stop_words]
        return ' '.join(tokens_limpios)

    df['texto_limpio'] = df['texto_original'].apply(limpiar_texto)
    
    df['label_num'] = df['label'].map({'ham': 0, 'spam': 1})
    
    df_final = df[['label_num', 'texto_limpio', 'num_caracteres', 'num_mayusculas', 'num_digitos']]

    print("Guardando datos procesados en la nueva tabla 'spam_limpio'...")
    df_final.to_sql('spam_limpio', engine, if_exists='replace', index=False)
    
    print("¡Fase 1 completada con éxito! Los datos están listos en la BD para la Fase 2.")
    return df_final

if __name__ == "__main__":
    ejecutar_fase_1_db()