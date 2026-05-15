from fase_1_db import ejecutar_fase_1_db
from fase_2 import ejecutar_fase_2, separar_variables
from fase_3 import ejecutar_fase_3
from fase_4 import ejecutar_fase_4
from fase_5 import ejecutar_fase_5


def ejecutar_pipeline_completo():
    print("=" * 60)
    print("PIPELINE DE CLASIFICACIÓN DE SPAM")
    print("=" * 60)

    print("\nEjecutando Fase 1")
    df_limpio = ejecutar_fase_1_db()

    print("\nEjecutando Fase 2")
    X_train, X_test, y_train, y_test, preprocesador = ejecutar_fase_2(df_limpio)

    print("\nEjecutando Fase 3")
    modelos_entrenados = ejecutar_fase_3(
        X_train,
        y_train,
        preprocesador,
    )

    print("\nEjecutando Fase 4")
    mejor_modelo, df_resultados = ejecutar_fase_4(
        modelos_entrenados,
        X_test,
        y_test,
    )

    print("\nEjecutando Fase 5")
    X_completo, y_completo = separar_variables(df_limpio)

    resultados_fase_5 = ejecutar_fase_5(
        X_completo,
        y_completo,
        preprocesador,
    )

    print("\nPipeline completado correctamente.")

    return {
        "df_limpio": df_limpio,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "preprocesador": preprocesador,
        "modelos_entrenados": modelos_entrenados,
        "mejor_modelo": mejor_modelo,
        "df_resultados": df_resultados,
        "resultados_fase_5": resultados_fase_5,
    }


if __name__ == "__main__":
    resultados = ejecutar_pipeline_completo()