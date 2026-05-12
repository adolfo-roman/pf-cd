import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier

def ejecutar_fase_3(ruta_x="X_train.csv", ruta_y="y_train.csv", ruta_prep="preprocesador_base.joblib"):
    print("Iniciando Fase 3: Entrenamiento Competitivo...")

    # 1. Cargar datos y evitar valores nulos residuales
    X_train = pd.read_csv(ruta_x)
    X_train['texto_limpio'] = X_train['texto_limpio'].fillna('')

    # .values.ravel() convierte el DataFrame de una columna a un arreglo 1D que scikit-learn prefiere
    y_train = pd.read_csv(ruta_y).values.ravel()

    # 2. Cargar el preprocesador de la Fase 2
    preprocesador = joblib.load(ruta_prep)

    # 3. Definir los algoritmos con mitigación de desbalance (class_weight='balanced')
    modelos = {
        'LogReg': LogisticRegression(class_weight='balanced', max_iter=1000),
        'NaiveBayes': MultinomialNB(), # NB maneja bien el texto por defecto
        'SVM': SVC(kernel='linear', class_weight='balanced', probability=True),
        'RandomForest': RandomForestClassifier(class_weight='balanced_subsample', random_state=42)
    }

    # 4. Entrenamiento y empaquetado
    for nombre, algoritmo in modelos.items():
        print(f"Entrenando candidato: {nombre}...")

        # El Pipeline une la transformación matemática y el algoritmo de IA en un solo paso
        pipe = Pipeline(steps=[
            ('preprocesamiento', preprocesador),
            ('clasificador', algoritmo)
        ])

        # Entrenar el pipeline completo
        pipe.fit(X_train, y_train)

        # 5. Exportar el candidato entrenado
        nombre_archivo = f"candidato_{nombre}.joblib"
        joblib.dump(pipe, nombre_archivo)
        print(f"Guardado: {nombre_archivo}")

    print("Fase 3 completada.")