# %%
# ============================================================
# PHASE 5: POWER BI DATASET GENERATION
# ============================================================
# This script is self-contained and rebuilds the inputs it needs from the
# reusable phase modules.
# It uses:
#   - fase_1_db.ejecutar_fase_1_db() to load the cleaned dataset
#   - fase_2.separar_variables() to obtain X and Y
#   - fase_2.crear_preprocesador() to build the shared preprocessor
#   - DATASET_VERSION (optional — defaults to "v1.0")
# Outputs three CSV files ready for Power BI:
#   - powerbi_experiment_results.csv
#   - powerbi_confusion_matrix.csv
#   - powerbi_hyperparameters.csv
# ============================================================

import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from fase_1_db import ejecutar_fase_1_db
from fase_2 import crear_preprocesador, separar_variables

from sklearn.base import clone
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)

# -------------------------------------------------------
# CONFIG — adjust as needed
# -------------------------------------------------------
# Rebuild the data inputs used by this phase from the earlier phases.
df_limpio = ejecutar_fase_1_db()
X, Y = separar_variables(df_limpio)
preprocessor = crear_preprocesador()

N_RUNS         = 5
DATASET_VERSION = "v1.0"
RUN_SEEDS      = [42, 7, 13, 99, 2024][:N_RUNS]

# Re-declare models (same hyperparams as Phase 3)
# so each run starts from an untrained estimator
_model_templates = {
    "Logistic Regression": LogisticRegression(
        class_weight="balanced", max_iter=1000, random_state=42
    ),
    "Naive Bayes": MultinomialNB(),
    "Support Vector Machine": LinearSVC(
        class_weight="balanced", random_state=42
    ),
    "Random Forest": RandomForestClassifier(
        class_weight="balanced_subsample", random_state=42
    ),
}

_base_pipelines = {
    name: Pipeline(steps=[("preprocessor", preprocessor), ("classifier", model)])
    for name, model in _model_templates.items()
}

# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------
def _get_hyperparams(pipeline):
    """Serialize classifier hyperparameters as a JSON string."""
    params = pipeline.named_steps["classifier"].get_params()
    return json.dumps({k: str(v) for k, v in params.items()})


def _evaluate_one(pipeline, X_tr, Y_tr, X_te, Y_te,
                  run_id, model_name):
    """Train a fresh clone and return a result row + CM rows."""
    p = clone(pipeline)

    # Train
    t0 = time.perf_counter()
    p.fit(X_tr, Y_tr)
    train_time = round(time.perf_counter() - t0, 4)

    # Predict
    t0 = time.perf_counter()
    y_pred = p.predict(X_te)
    inf_time = round(time.perf_counter() - t0, 6)

    # AUC — works for models with predict_proba or decision_function
    clf = p.named_steps["classifier"]
    try:
        scores = (p.predict_proba(X_te)[:, 1]
                  if hasattr(clf, "predict_proba")
                  else p.decision_function(X_te))
        auc = round(roc_auc_score(Y_te, scores), 6)
    except Exception:
        auc = None

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(Y_te, y_pred).ravel()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "run_id"             : run_id,
        "model_name"         : model_name,
        "accuracy"           : round(accuracy_score(Y_te, y_pred), 6),
        "precision"          : round(precision_score(Y_te, y_pred, zero_division=0), 6),
        "recall"             : round(recall_score(Y_te, y_pred, zero_division=0), 6),
        "f1_score"           : round(f1_score(Y_te, y_pred, zero_division=0), 6),
        "auc"                : auc,
        "tp"                 : int(tp),
        "fp"                 : int(fp),
        "tn"                 : int(tn),
        "fn"                 : int(fn),
        "training_time_sec"  : train_time,
        "inference_time_sec" : inf_time,
        "dataset_version"    : DATASET_VERSION,
        "date_trained"       : now,
        "is_best_model"      : False,   # filled below
        "is_production_model": False,   # filled below
        "hyperparameters"    : _get_hyperparams(p),
        # internal — original selection formula: recall - FP penalty
        "_sel_score"         : round(recall_score(Y_te, y_pred, zero_division=0) - fp * 0.1, 6),
    }

    # Confusion matrix in tidy / long format
    labels = ["ham (0)", "spam (1)"]
    cm_raw = confusion_matrix(Y_te, y_pred)
    cm_rows = [
        {
            "run_id"         : run_id,
            "model_name"     : model_name,
            "actual_class"   : labels[i],
            "predicted_class": labels[j],
            "count"          : int(cm_raw[i][j]),
            "date_trained"   : now,
        }
        for i in range(2) for j in range(2)
    ]

    return row, cm_rows


# -------------------------------------------------------
# MULTI-RUN LOOP
# -------------------------------------------------------
all_rows   = []
all_cm     = []

print(f"\n{'='*60}")
print(f"  Phase 6 — {N_RUNS} runs × {len(_base_pipelines)} models")
print(f"{'='*60}")

for idx, seed in enumerate(RUN_SEEDS):
    run_id = f"run_{idx+1:02d}_seed{seed}"
    print(f"\n--- Run {idx+1}/{N_RUNS}  (seed={seed}) ---")

    X_tr, X_te, Y_tr, Y_te = train_test_split(
        X, Y, test_size=0.2, stratify=Y, random_state=seed
    )

    run_best_score = -999
    run_best_name  = None

    for name, pipe in _base_pipelines.items():
        row, cm_rows = _evaluate_one(pipe, X_tr, Y_tr, X_te, Y_te, run_id, name)
        all_rows.append(row)
        all_cm.extend(cm_rows)

        if row["_sel_score"] > run_best_score:
            run_best_score = row["_sel_score"]
            run_best_name  = name

        print(f"  {name:<28} acc={row['accuracy']:.4f}  "
              f"prec={row['precision']:.4f}  rec={row['recall']:.4f}  "
              f"f1={row['f1_score']:.4f}  auc={str(row['auc'])[:6]}")

    # Mark best model within this run
    for r in all_rows:
        if r["run_id"] == run_id and r["model_name"] == run_best_name:
            r["is_best_model"] = True

    print(f"  → Best in run: {run_best_name}")

# Mark production model (winner of the canonical seed=42 run)
canonical_rows = [r for r in all_rows if r["run_id"] == "run_01_seed42"]
prod_model = max(canonical_rows, key=lambda r: r["_sel_score"])["model_name"]

for r in all_rows:
    if r["model_name"] == prod_model:
        r["is_production_model"] = True

# -------------------------------------------------------
# BUILD & EXPORT DATAFRAMES
# -------------------------------------------------------

# Table 1 — Main results
df_results = pd.DataFrame(all_rows).drop(columns=["_sel_score"])

# Table 2 — Confusion matrix (tidy)
df_cm = pd.DataFrame(all_cm)

# Table 3 — Hyperparameters expanded (one column per param)
_hp_expanded = df_results["hyperparameters"].apply(json.loads)
_hp_df       = pd.json_normalize(_hp_expanded).add_prefix("hp_")
df_hyperparams = pd.concat(
    [df_results[["run_id", "model_name", "date_trained"]].reset_index(drop=True),
     _hp_df.reset_index(drop=True)],
    axis=1,
)

df_results.to_csv("./dashboard/experiment_results.csv",  index=False)
df_cm.to_csv("./dashboard/confusion_matrix.csv",         index=False)
df_hyperparams.to_csv("./dashboard/hyperparameters.csv", index=False)

print(f"\n{'='*60}")
print("  Power BI datasets exported:")
print("  → powerbi_experiment_results.csv")
print("  → powerbi_confusion_matrix.csv")
print("  → powerbi_hyperparameters.csv")
print(f"{'='*60}")

# Quick summary
print("\n--- Mean performance across runs ---")
print(
    df_results
    .groupby("model_name")[["accuracy", "precision", "recall", "f1_score", "auc"]]
    .mean()
    .round(4)
    .to_string()
)