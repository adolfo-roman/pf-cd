from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

RAW_TABLE_NAME = "spam_raw"

RANDOM_STATE = 42
TEST_SIZE = 0.2
MAX_FEATURES_TFIDF = 3000


def validar_variables_entorno():
    variables_requeridas = {
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_HOST": DB_HOST,
        "DB_PORT": DB_PORT,
        "DB_NAME": DB_NAME,
    }

    variables_faltantes = [
        nombre
        for nombre, valor in variables_requeridas.items()
        if not valor
    ]

    if variables_faltantes:
        raise ValueError(
            "Faltan variables en el archivo .env: "
            + ", ".join(variables_faltantes)
        )


validar_variables_entorno()