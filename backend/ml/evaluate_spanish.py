"""
evaluate_spanish.py
===================
Evalúa el modelo de phishing entrenado solo sobre los correos en español
del conjunto de test, para medir el rendimiento real en ese subconjunto
del corpus.

Reproduce el mismo split (random_state=42, test_size=0.2, stratify=y)
que se usa en train.py y compare_models.py, de modo que la evaluación
se realiza sobre correos que el modelo no ha visto durante el entrenamiento.

Uso
---
  python -m backend.ml.evaluate_spanish
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "emails.csv"
MODEL_PATH = Path(__file__).resolve().parent / "phishing_model.joblib"


def main() -> None:
    print(f"Cargando dataset de {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)

    if "lang" not in df.columns:
        raise ValueError(
            "El dataset no tiene la columna 'lang'. Vuelve a generarlo con build_dataset.py."
        )

    X = df["text"].astype(str)
    y = df["label"].astype(int)
    lang = df["lang"].astype(str)

    # Reproducimos el mismo split que train.py / compare_models.py
    X_train, X_test, y_train, y_test, lang_train, lang_test = train_test_split(
        X, y, lang, test_size=0.2, random_state=42, stratify=y
    )

    # Filtramos solo los correos en español del set de test
    mask_es = lang_test == "es"
    X_test_es = X_test[mask_es]
    y_test_es = y_test[mask_es]

    n_es = len(X_test_es)
    n_phish = int((y_test_es == 1).sum())
    n_legit = int((y_test_es == 0).sum())

    print()
    print("=" * 60)
    print("EVALUACIÓN DEL MODELO SOBRE CORREOS EN ESPAÑOL (TEST SET)")
    print("=" * 60)
    print(f"Total correos en español en test : {n_es}")
    print(f"  - Phishing                    : {n_phish}")
    print(f"  - Legítimos                   : {n_legit}")
    print()

    if n_es == 0:
        print("No hay correos en español en el conjunto de test.")
        return

    print(f"Cargando modelo desde {MODEL_PATH} ...")
    model = joblib.load(MODEL_PATH)

    print("Realizando predicciones ...")
    y_pred_es = model.predict(X_test_es)

    accuracy = accuracy_score(y_test_es, y_pred_es)
    precision_macro = precision_score(y_test_es, y_pred_es, average="macro", zero_division=0)
    recall_macro = recall_score(y_test_es, y_pred_es, average="macro", zero_division=0)
    f1_macro = f1_score(y_test_es, y_pred_es, average="macro", zero_division=0)

    print()
    print("--- Métricas globales (solo español) ---")
    print(f"Accuracy        : {accuracy:.4f}")
    print(f"Precision macro : {precision_macro:.4f}")
    print(f"Recall macro    : {recall_macro:.4f}")
    print(f"F1 macro        : {f1_macro:.4f}")
    print()
    print("--- Reporte detallado por clase ---")
    print(
        classification_report(
            y_test_es,
            y_pred_es,
            target_names=["legítimo", "phishing"],
            digits=4,
            zero_division=0,
        )
    )
    print("--- Matriz de confusión ---")
    print("                Predicho")
    print("              legit  phish")
    cm = confusion_matrix(y_test_es, y_pred_es, labels=[0, 1])
    print(f"Real legit    {cm[0, 0]:5d}  {cm[0, 1]:5d}")
    print(f"Real phish    {cm[1, 0]:5d}  {cm[1, 1]:5d}")
    print()

    # Comparación de referencia: cómo va el modelo sobre el set de test completo
    print("=" * 60)
    print("REFERENCIA: rendimiento sobre el TEST SET COMPLETO")
    print("=" * 60)
    y_pred_all = model.predict(X_test)
    print(f"Accuracy        : {accuracy_score(y_test, y_pred_all):.4f}")
    print(
        f"F1 macro        : "
        f"{f1_score(y_test, y_pred_all, average='macro', zero_division=0):.4f}"
    )


if __name__ == "__main__":
    main()
