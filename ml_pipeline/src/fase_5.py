import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


def _get_hyperparams(pipeline):
    params = pipeline.named_steps["classifier"].get_params()
    return json.dumps({k: str(v) for k, v in params.items()})


def _evaluate_one(pipeline, X_train, y_train, X_test, y_test, run_id, model_name):
    trained_pipeline = clone(pipeline)

    train_start = time.perf_counter()
    trained_pipeline.fit(X_train, y_train)
    train_time = round(time.perf_counter() - train_start, 4)

    predict_start = time.perf_counter()
    y_pred = trained_pipeline.predict(X_test)
    inference_time = round(time.perf_counter() - predict_start, 6)

    classifier = trained_pipeline.named_steps["classifier"]
    try:
        if hasattr(classifier, "predict_proba"):
            scores = trained_pipeline.predict_proba(X_test)[:, 1]
        else:
            scores = trained_pipeline.decision_function(X_test)
        auc = round(roc_auc_score(y_test, scores), 6)
    except Exception:
        auc = None

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    result_row = {
        "run_id": run_id,
        "model_name": model_name,
        "accuracy": round(accuracy_score(y_test, y_pred), 6),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 6),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 6),
        "f1_score": round(f1_score(y_test, y_pred, zero_division=0), 6),
        "auc": auc,
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "training_time_sec": train_time,
        "inference_time_sec": inference_time,
        "dataset_version": "v1.0",
        "date_trained": timestamp,
        "is_best_model": False,
        "is_production_model": False,
        "hyperparameters": _get_hyperparams(trained_pipeline),
        "_sel_score": round(recall_score(y_test, y_pred, zero_division=0) - fp * 0.1, 6),
    }

    labels = ["ham (0)", "spam (1)"]
    cm_raw = confusion_matrix(y_test, y_pred)
    cm_rows = [
        {
            "run_id": run_id,
            "model_name": model_name,
            "actual_class": labels[i],
            "predicted_class": labels[j],
            "count": int(cm_raw[i][j]),
            "date_trained": timestamp,
        }
        for i in range(2)
        for j in range(2)
    ]

    return result_row, cm_rows


def ejecutar_fase_5(X, Y, preprocessor, output_dir=".", dataset_version="v1.0"):
    print("Iniciando Fase 5: generación de datasets para Power BI")

    model_templates = {
        "Logistic Regression": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        ),
        "Naive Bayes": MultinomialNB(),
        "Support Vector Machine": LinearSVC(
            class_weight="balanced",
            random_state=42,
        ),
        "Random Forest": RandomForestClassifier(
            class_weight="balanced_subsample",
            random_state=42,
        ),
    }

    base_pipelines = {
        name: Pipeline(steps=[("preprocessor", preprocessor), ("classifier", model)])
        for name, model in model_templates.items()
    }

    n_runs = 5
    run_seeds = [42, 7, 13, 99, 2024][:n_runs]

    all_rows = []
    all_cm = []

    print(f"\n{'=' * 60}")
    print(f"  Phase 5 — {n_runs} runs × {len(base_pipelines)} models")
    print(f"{'=' * 60}")

    for index, seed in enumerate(run_seeds):
        run_id = f"run_{index + 1:02d}_seed{seed}"
        print(f"\n--- Run {index + 1}/{n_runs}  (seed={seed}) ---")

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            Y,
            test_size=0.2,
            stratify=Y,
            random_state=seed,
        )

        run_best_score = -999
        run_best_name = None

        for model_name, pipeline in base_pipelines.items():
            row, cm_rows = _evaluate_one(
                pipeline,
                X_train,
                y_train,
                X_test,
                y_test,
                run_id,
                model_name,
            )

            all_rows.append(row)
            all_cm.extend(cm_rows)

            if row["_sel_score"] > run_best_score:
                run_best_score = row["_sel_score"]
                run_best_name = model_name

            print(
                f"  {model_name:<28} acc={row['accuracy']:.4f}  "
                f"prec={row['precision']:.4f}  rec={row['recall']:.4f}  "
                f"f1={row['f1_score']:.4f}  auc={str(row['auc'])[:6]}"
            )

        for result in all_rows:
            if result["run_id"] == run_id and result["model_name"] == run_best_name:
                result["is_best_model"] = True

        print(f"  → Best in run: {run_best_name}")

    canonical_rows = [row for row in all_rows if row["run_id"] == "run_01_seed42"]
    production_model = max(canonical_rows, key=lambda row: row["_sel_score"])["model_name"]

    for result in all_rows:
        if result["model_name"] == production_model:
            result["is_production_model"] = True

    df_results = pd.DataFrame(all_rows).drop(columns=["_sel_score"])
    df_cm = pd.DataFrame(all_cm)

    hyperparams_expanded = df_results["hyperparameters"].apply(json.loads)
    hyperparams_df = pd.json_normalize(hyperparams_expanded).add_prefix("hp_")
    df_hyperparams = pd.concat(
        [
            df_results[["run_id", "model_name", "date_trained"]].reset_index(drop=True),
            hyperparams_df.reset_index(drop=True),
        ],
        axis=1,
    )

    results_path = f"{output_dir}/dashboard/experiment_results.csv"
    cm_path = f"{output_dir}/dashboard/confusion_matrix.csv"
    hyperparams_path = f"{output_dir}/dashboard/hyperparameters.csv"

    df_results.to_csv(results_path, index=False)
    df_cm.to_csv(cm_path, index=False)
    df_hyperparams.to_csv(hyperparams_path, index=False)

    print(f"\n{'=' * 60}")
    print("  Power BI datasets exported:")
    print("  → dashboard/experiment_results.csv")
    print("  → dashboard/confusion_matrix.csv")
    print("  → dashboard/hyperparameters.csv")
    print(f"{'=' * 60}")

    print("\n--- Mean performance across runs ---")
    print(
        df_results.groupby("model_name")[["accuracy", "precision", "recall", "f1_score", "auc"]]
        .mean()
        .round(4)
        .to_string()
    )

    return {
        "df_results": df_results,
        "df_confusion_matrix": df_cm,
        "df_hyperparameters": df_hyperparams,
        "production_model": production_model,
    }


if __name__ == "__main__":
    from fase_1_db import ejecutar_fase_1_db
    from fase_2 import crear_preprocesador, separar_variables

    df_limpio = ejecutar_fase_1_db()
    X, Y = separar_variables(df_limpio)
    preprocessor = crear_preprocesador()

    ejecutar_fase_5(X, Y, preprocessor)