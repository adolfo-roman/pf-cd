# ============================================================
# FASE 4: EVALUACIÓN DE NEGOCIO Y CONTROL DE CALIDAD (QA)
# ============================================================
import os
import sys
import joblib  # Importación necesaria para el framework de tu equipo

# ------------------------------------------------------------
# CONFIGURACIÓN DE RUTAS AUTOMÁTICA
# ------------------------------------------------------------
# 1. Obtenemos la ruta de la carpeta actual (Fase04)
ruta_actual = os.getcwd()

# 2. Subimos un nivel y entramos a Fase03
ruta_fase03 = os.path.join(os.path.dirname(ruta_actual), "Fase03")

# 3. Agregamos Fase03 al sistema para que Python encuentre los archivos/módulos
if os.path.exists(ruta_fase03):
    sys.path.append(ruta_fase03)
    print(f"Ruta vinculada exitosamente: {ruta_fase03}")
else:
    print(f"⚠️ Alerta: No se encontró la carpeta {ruta_fase03}. Verifica que los nombres sean exactos.")

import numpy as np
import json
from sklearn.metrics import confusion_matrix, precision_score, recall_score

# NOTA: Este código asume que 'trained_models' viene de la Fase 3 
# y 'X_test', 'Y_test' son los datos de validación. [cite: 120, 121, 122]

print("--- Iniciando Fase 4: Auditoría y Empaquetado ---")

# 1. EVALUACIÓN "ZERO TRUST" Y SELECCIÓN [cite: 125]
# ------------------------------------------------------------
best_model_name = ""
best_pipeline = None
best_score = -1
metrics_log = "--- Log de Evaluación de Negocio y QA ---\n\n"

for name, model in trained_models.items():
    y_pred = model.predict(X_test) # [cite: 110]
    
    cm = confusion_matrix(Y_test, y_pred) # [cite: 126]
    precision = precision_score(Y_test, y_pred, zero_division=0) # [cite: 127]
    recall = recall_score(Y_test, y_pred, zero_division=0) # [cite: 127]
    
    # REGLA ESTRICTA DEL PDF: El modelo que logre la mayor detección de Spam (Recall) 
    # manteniendo los Falsos Positivos (cm[0][1]) en CERO. [cite: 128]
    if cm[0][1] == 0:
        score = recall
    else:
        score = -1  # Penalización total por tener falsos positivos [cite: 128]

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

# 2. EMPAQUETADO EN PIPELINE [cite: 130]
# ------------------------------------------------------------
# Al usar el objeto 'model' que ya incluye el preprocessor, 
# garantizamos que el empaquetado sea una sola estructura. [cite: 131, 133]
modelo_final = best_pipeline 

# 3. EXPORTACIÓN A FORMATO JOBLIB (Sustituye ONNX)
# ------------------------------------------------------------
print("Exportando pipeline a formato .joblib para el framework...")
try:
    # Entregable: modelo_produccion.joblib
    joblib.dump(modelo_final, 'modelo_produccion.joblib')
    print("Éxito: 'modelo_produccion.joblib' generado.")
except Exception as e:
    print(f"Error en exportación Joblib: {e}")

# 4. ACTUALIZACIÓN DEL CONTROL DE CACHÉ [cite: 138]
# ------------------------------------------------------------
try:
    with open("version.json", "r") as f:
        v_data = json.load(f)
        v_actual = v_data.get("version", 0) # [cite: 123, 139]
except FileNotFoundError:
    v_actual = 0

nueva_version = v_actual + 1 # [cite: 139]

# Entregable: version.json actualizado [cite: 139, 144]
with open("version.json", "w") as f:
    json.dump({"version": nueva_version}, f)

# Entregable: metricas_entrenamiento.txt [cite: 145]
with open("metricas_entrenamiento.txt", "w") as f:
    f.write(metrics_log)

print(f"Control de caché actualizado a versión: {nueva_version}")
print("Fase 4 finalizada. Archivos listos para el repositorio.")