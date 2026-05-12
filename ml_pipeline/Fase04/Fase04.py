# ============================================================
# FASE 4: EVALUACIÓN DE NEGOCIO Y CONTROL DE CALIDAD (QA)
# ============================================================

import numpy as np
import json
from sklearn.metrics import confusion_matrix, precision_score, recall_score
from skl2onnx import to_onnx
from skl2onnx.common.data_types import StringTensorType, FloatTensorType

# NOTA: Este código asume que 'trained_models' viene de la Fase 3 
# y 'X_test', 'Y_test' son los datos de validación.

print("--- Iniciando Fase 4: Auditoría y Empaquetado ---")

# 1. EVALUACIÓN "ZERO TRUST" Y SELECCIÓN
# ------------------------------------------------------------
best_model_name = ""
best_pipeline = None
best_score = -1
metrics_log = "--- Log de Evaluación de Negocio y QA ---\n\n"

for name, model in trained_models.items():
    y_pred = model.predict(X_test)
    
    cm = confusion_matrix(Y_test, y_pred)
    precision = precision_score(Y_test, y_pred, zero_division=0)
    recall = recall_score(Y_test, y_pred, zero_division=0)
    
    # REGLA ESTRICTA DEL PDF: El modelo que logre la mayor detección de Spam (Recall) 
    # manteniendo los Falsos Positivos (cm[0][1]) en CERO.
    if cm[0][1] == 0:
        score = recall
    else:
        score = -1  # Penalización total por tener falsos positivos

    log_entry = (
        f"Modelo: {name}\n"
        f"Precision: {precision:.4f} | Recall: {recall:.4f}\n"
        f"Matriz de Confusión:\n{cm}\n\n"
    )
    metrics_log += log_entry
    
    if score > best_score:
        best_score = score
        best_pipeline = model
        best_model_name = name

print(f"Ganador seleccionado bajo regla estricta: {best_model_name}")

# 2. EMPAQUETADO EN PIPELINE
# ------------------------------------------------------------
# Al usar el objeto 'model' que ya incluye el preprocessor, 
# garantizamos que el empaquetado sea una sola estructura.
modelo_final = best_pipeline 

# 3. TRANSCODIFICACIÓN A FORMATO EDGE (ONNX)
# ------------------------------------------------------------
print("Convirtiendo pipeline a formato binario .onnx...")
try:
    # Definición de tipos de entrada para el modelo web
    initial_types = [
        ('clean_text', StringTensorType([None, 1])),
        ('message_length', FloatTensorType([None, 1])),
        ('num_uppercase', FloatTensorType([None, 1])),
        ('num_digits', FloatTensorType([None, 1]))
    ]

    # Conversión técnica usando skl2onnx
    onnx_model = to_onnx(modelo_final, initial_types=initial_types)
    
    # Entregable: modelo_produccion.onnx
    with open("modelo_produccion.onnx", "wb") as f:
        f.write(onnx_model.SerializeToString())
    print("Éxito: 'modelo_produccion.onnx' generado.")
except Exception as e:
    print(f"Error en conversión ONNX: {e}")

# 4. ACTUALIZACIÓN DEL CONTROL DE CACHÉ
# ------------------------------------------------------------
try:
    with open("version.json", "r") as f:
        v_data = json.load(f)
        v_actual = v_data.get("version", 0)
except FileNotFoundError:
    v_actual = 0

nueva_version = v_actual + 1

# Entregable: version.json actualizado
with open("version.json", "w") as f:
    json.dump({"version": nueva_version}, f)

# Entregable: metricas_entrenamiento.txt
with open("metricas_entrenamiento.txt", "w") as f:
    f.write(metrics_log)

print(f"Control de caché actualizado a versión: {nueva_version}")
print("Fase 4 finalizada. Archivos listos para el repositorio.")