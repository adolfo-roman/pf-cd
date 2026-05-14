import joblib
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

from config import MODELS_DIR


def evaluar_modelo(nombre, modelo, X_test, y_test):
    y_pred = modelo.predict(X_test)

    metricas = {
        "modelo": nombre,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1_score": f1_score(y_test, y_pred),
    }

    print("\n" + "=" * 60)
    print(f"Evaluación del modelo: {nombre}")
    print("=" * 60)

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

    return metricas


def evaluar_modelos(modelos_entrenados, X_test, y_test):
    resultados = []

    for nombre, modelo in modelos_entrenados.items():
        metricas = evaluar_modelo(
            nombre,
            modelo,
            X_test,
            y_test,
        )

        resultados.append(metricas)

    df_resultados = pd.DataFrame(resultados)

    df_resultados = df_resultados.sort_values(
        by="f1_score",
        ascending=False,
    )

    return df_resultados


def seleccionar_mejor_modelo(df_resultados, modelos_entrenados):
    mejor_nombre = df_resultados.iloc[0]["modelo"]
    mejor_modelo = modelos_entrenados[mejor_nombre]

    return mejor_nombre, mejor_modelo


def guardar_mejor_modelo(mejor_modelo):
    ruta_modelo_final = MODELS_DIR / "modelo_final.joblib"

    joblib.dump(mejor_modelo, ruta_modelo_final)

    print(f"\nMejor modelo guardado en: {ruta_modelo_final}")


def ejecutar_fase_4(modelos_entrenados, X_test, y_test):
    print("Iniciando Fase 4: evaluación y selección del mejor modelo")

    df_resultados = evaluar_modelos(
        modelos_entrenados,
        X_test,
        y_test,
    )

    mejor_nombre, mejor_modelo = seleccionar_mejor_modelo(
        df_resultados,
        modelos_entrenados,
    )

    guardar_mejor_modelo(mejor_modelo)

    print("\nResumen de resultados:")
    print(df_resultados)

    print(f"\nMejor modelo seleccionado: {mejor_nombre}")
    print("Fase 4 completada.")

    return mejor_modelo, df_resultados