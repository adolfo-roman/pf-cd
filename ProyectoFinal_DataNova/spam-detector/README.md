# AEGIS — SMS Spam Classifier 🛡️

Sistema de clasificación de SMS mediante Machine Learning.
Proyecto final · Temas Selectos de Computación III · UNAM × Kyndryl · 2026

---

## Estructura del repositorio

```
spam-detector/
│
├── app/                        ← Aplicación Flask
│   ├── __init__.py             ← Factory de la app (create_app)
│   ├── routes.py               ← Rutas HTTP y API REST
│   ├── predictor.py            ← Pipeline NLP + inferencia del modelo
│   │
│   ├── templates/              ← HTML (Jinja2)
│   │   ├── base.html           ← Layout base (nav, footer)
│   │   ├── index.html          ← Analizador de SMS
│   │   ├── dashboard.html      ← Métricas de modelos
│   │   └── about.html          ← Documentación del proyecto
│   │
│   └── static/
│       ├── css/main.css        ← Estilos (dark industrial)
│       └── js/
│           ├── main.js         ← Utilidades globales
│           ├── analyzer.js     ← Lógica del analizador (fetch API)
│           └── dashboard.js    ← Animaciones del dashboard
│
├── ml_pipeline/
│   ├── models/
│   │   ├── modelo_final.joblib       ← Modelo en producción (SVM)
│   │   └── candidato_*.joblib        ← Modelos candidatos evaluados
│   └── src/                          ← Scripts de entrenamiento
│       ├── config.py
│       ├── cargar_datos.py
│       ├── fase_1_db.py
│       ├── fase_2.py
│       ├── fase_3.py
│       ├── fase_4.py
│       └── pipeline.py
│
├── data/
│   ├── experiment_results.csv  ← Métricas de todos los experimentos
│   └── confusion_matrix.csv    ← Matrices de confusión por modelo/run
│
├── run.py                      ← Punto de entrada (desarrollo)
├── requirements.txt            ← Dependencias Python
├── .gitignore
└── README.md
```

---

## Instalación y ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/spam-detector.git
cd spam-detector
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Ejecutar la aplicación

```bash
python run.py
```

Visita [http://localhost:5000](http://localhost:5000)

---

## API REST

### `POST /api/predict`

Clasifica un SMS en spam o ham.

**Request:**
```json
{ "text": "URGENT! You won £1000. Call 08002986030 NOW." }
```

**Response:**
```json
{
  "label":      "spam",
  "is_spam":    true,
  "confidence": 99.9,
  "spam_prob":  99.9,
  "ham_prob":   0.1,
  "clean_text": "urgent won call now",
  "stats": {
    "num_chars":     44,
    "num_uppercase": 8,
    "num_digits":    11
  }
}
```

### `GET /api/metrics`

Devuelve métricas promedio de todos los modelos evaluados.

---

## Pipeline NLP

```
Texto crudo
    → Limpieza de ruido (regex)
    → Normalización a minúsculas
    → Eliminación de stop-words
    → Stemming
    → TF-IDF (3,000 features)
    → + Features numéricas (longitud, mayúsculas, dígitos)
    → ColumnTransformer (MinMaxScaler + TfidfVectorizer)
    → SVM (kernel lineal, class_weight='balanced')
    → Predicción binaria (0=ham, 1=spam)
```

---

## Resultados

| Modelo            | Accuracy | Precision | F1-Score | AUC-ROC |
|-------------------|----------|-----------|----------|---------|
| Naive Bayes       | ~92%     | **99.5%** | ~84%     | 99.7%   |
| SVM               | **98.5%**| 96.0%     | **97.4%**| 99.8%   |
| Random Forest     | 96.8%    | 94.3%     | 94.6%    | 99.5%   |
| Logistic Reg.     | 96.1%    | 89.5%     | 93.8%    | 99.7%   |

> **Modelo en producción:** Naive Bayes (máxima Precisión → mínimos falsos positivos)

---

## Equipo

| Rol | Responsabilidad |
|-----|----------------|
| PM & MLOps | Orquestación, Git, despliegue |
| Data Engineer | Preprocesamiento NLP |
| Data Analyst | EDA, visualizaciones |
| Data Scientist | Modelado, hiperparámetros |
| QA / Business Analyst | Métricas, ROI |
| UX / UI | Frontend, presentación |

---

## Contexto

Este proyecto se desarrolla en colaboración con **Kyndryl**, empresa líder global en
infraestructura de TI, como parte de un proceso de evaluación y reclutamiento para
estudiantes de la Facultad de Ingeniería de la UNAM.
