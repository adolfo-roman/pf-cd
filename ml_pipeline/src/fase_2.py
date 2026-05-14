import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler
from sklearn.compose import ColumnTransformer


def separar_variables(df_limpio):
    df = df_limpio.copy()

    df["texto_limpio"] = df["texto_limpio"].fillna("")

    X = df[
        [
            "texto_limpio",
            "num_caracteres",
            "num_mayusculas",
            "num_digitos",
        ]
    ]

    y = df["label_num"]

    return X, y


def dividir_train_test(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    return X_train, X_test, y_train, y_test


def crear_preprocesador():
    preprocesador = ColumnTransformer(
        transformers=[
            (
                "texto",
                TfidfVectorizer(max_features=3000),
                "texto_limpio",
            ),
            (
                "numeros",
                MinMaxScaler(),
                [
                    "num_caracteres",
                    "num_mayusculas",
                    "num_digitos",
                ],
            ),
        ]
    )

    return preprocesador


def ejecutar_fase_2(df_limpio):
    print("Iniciando Fase 2: Vectorización base y partición train/test")

    X, y = separar_variables(df_limpio)

    X_train, X_test, y_train, y_test = dividir_train_test(X, y)

    preprocesador = crear_preprocesador()

    print("Fase 2 completada.")
    print(f"Dimensiones de entrenamiento: {X_train.shape[0]} filas.")
    print(f"Dimensiones de prueba: {X_test.shape[0]} filas.")

    return X_train, X_test, y_train, y_test, preprocesador