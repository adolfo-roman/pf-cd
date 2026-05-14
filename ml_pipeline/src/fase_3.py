import joblib

from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier

from config import MODELS_DIR, RANDOM_STATE


def definir_modelos():
    modelos = {
        "LogReg": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=RANDOM_STATE,
        ),
        "NaiveBayes": MultinomialNB(),
        "SVM": SVC(
            kernel="linear",
            class_weight="balanced",
            probability=True,
            random_state=RANDOM_STATE,
        ),
        "RandomForest": RandomForestClassifier(
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
        ),
    }

    return modelos


def entrenar_modelos(X_train, y_train, preprocesador, modelos):
    modelos_entrenados = {}

    for nombre, algoritmo in modelos.items():
        print(f"Entrenando candidato: {nombre}...")

        pipe = Pipeline(
            steps=[
                ("preprocesamiento", preprocesador),
                ("clasificador", algoritmo),
            ]
        )

        pipe.fit(X_train, y_train)

        ruta_modelo = MODELS_DIR / f"candidato_{nombre}.joblib"
        joblib.dump(pipe, ruta_modelo)

        modelos_entrenados[nombre] = pipe

        print(f"Guardado: {ruta_modelo}")

    return modelos_entrenados


def ejecutar_fase_3(X_train, y_train, preprocesador):
    print("Iniciando Fase 3: entrenamiento competitivo")

    modelos = definir_modelos()

    modelos_entrenados = entrenar_modelos(
        X_train,
        y_train,
        preprocesador,
        modelos,
    )

    print("Fase 3 completada.")

    return modelos_entrenados