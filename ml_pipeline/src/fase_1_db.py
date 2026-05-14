import re
import nltk
import numpy as np
import pandas as pd

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sqlalchemy import create_engine

from config import (
    DB_USER,
    DB_PASSWORD,
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_SSLMODE,
    RAW_TABLE_NAME,
)


nltk.download("stopwords", quiet=True)
nltk.download("wordnet", quiet=True)


def crear_conexion():
    db_url = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?sslmode={DB_SSLMODE}"
    )

    engine = create_engine(db_url)

    return engine


def extraer_datos_crudos(engine):
    query = f"""
    SELECT
        v1 AS label,
        v2 AS texto_original
    FROM {RAW_TABLE_NAME}
    """

    df_raw = pd.read_sql(query, engine)

    return df_raw


def limpiar_texto(texto, stop_words, lemmatizer):
    texto = re.sub(r"http\S+", "", str(texto))
    texto = re.sub(r"[^a-zA-Z]", " ", texto)

    tokens = texto.lower().split()

    tokens_limpios = [
        lemmatizer.lemmatize(word)
        for word in tokens
        if word not in stop_words
    ]

    return " ".join(tokens_limpios)


def transformar_datos(df_raw):
    df = df_raw.copy()

    df = df.drop_duplicates()
    df = df.dropna(subset=["label", "texto_original"])

    print("Calculando metadatos...")

    df["num_caracteres"] = df["texto_original"].apply(len).astype(np.float32)

    df["num_mayusculas"] = df["texto_original"].apply(
        lambda x: sum(1 for c in str(x) if c.isupper())
    ).astype(np.float32)

    df["num_digitos"] = df["texto_original"].apply(
        lambda x: sum(1 for c in str(x) if c.isdigit())
    ).astype(np.float32)

    print("Aplicando limpieza NLP...")

    stop_words = set(stopwords.words("english"))
    lemmatizer = WordNetLemmatizer()

    df["texto_limpio"] = df["texto_original"].apply(
        lambda texto: limpiar_texto(texto, stop_words, lemmatizer)
    )

    df["label_num"] = df["label"].map(
        {
            "ham": 0,
            "spam": 1,
        }
    )

    df_limpio = df[
        [
            "label_num",
            "texto_limpio",
            "num_caracteres",
            "num_mayusculas",
            "num_digitos",
        ]
    ]

    df_limpio = df_limpio.dropna(subset=["label_num"])

    return df_limpio


def ejecutar_fase_1_db():
    print("Iniciando Fase 1: extracción y limpieza desde BD")

    engine = crear_conexion()

    print("Extrayendo datos crudos desde la BD...")
    df_raw = extraer_datos_crudos(engine)

    print("Transformando datos crudos en DataFrame limpio...")
    df_limpio = transformar_datos(df_raw)

    print("Fase 1 completada.")
    print(f"Filas crudas: {len(df_raw)}")
    print(f"Filas limpias: {len(df_limpio)}")

    return df_limpio


if __name__ == "__main__":
    df_limpio = ejecutar_fase_1_db()
    print(df_limpio.head())