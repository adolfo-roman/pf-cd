import os
import pandas as pd

from dotenv import load_dotenv
from sqlalchemy import create_engine


load_dotenv()


def crear_conexion():
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_sslmode = os.getenv("DB_SSLMODE", "require")

    db_url = (
        f"postgresql://{db_user}:{db_password}"
        f"@{db_host}:{db_port}/{db_name}"
        f"?sslmode={db_sslmode}"
    )

    engine = create_engine(db_url)

    return engine


def cargar_datos_a_postgres():
    print("Iniciando lectura del archivo CSV...")

    df = pd.read_csv("data/spam.csv", encoding="latin-1")

    df = df[["v1", "v2"]]

    engine = crear_conexion()

    print("Conectando a la base de datos y subiendo información...")

    df.to_sql(
        "spam_raw",
        engine,
        if_exists="replace",
        index=True,
        index_label="id",
    )

    print(f"Éxito. Se cargaron {len(df)} registros en la tabla 'spam_raw'.")


if __name__ == "__main__":
    cargar_datos_a_postgres()