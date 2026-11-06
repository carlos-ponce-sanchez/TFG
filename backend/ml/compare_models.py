"""
compare_models.py
=================
Compara cuatro clasificadores sobre el mismo dataset y con las mismas
features TF-IDF, garantizando una comparación justa.

Modelos evaluados
-----------------
  1. Regresión Logística   (baseline, modelo lineal interpretable)
  2. SVM Lineal            (LinearSVC calibrado para obtener probabilidades)
  3. Random Forest         (ensamble de árboles de decisión)
  4. Red Neuronal MLP      (Multilayer Perceptron, 2 capas ocultas)

Salidas
-------
  data/resultados_modelos.csv   – tabla comparativa con métricas
  data/resultados_modelos.json  – detalle completo (matrices de confusión, etc.)
  backend/ml/phishing_model.joblib – pipeline del mejor modelo (reemplaza al anterior)

Uso
---
  python -m backend.ml.compare_models
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from backend.ml.preprocessing import TextPreprocessor
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "emails.csv"
RESULTS_DIR = BASE_DIR / "data"
MODEL_OUTPUT_PATH = Path(__file__).resolve().parent / "phishing_model.joblib"

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Límite de muestreo estratificado. Si el dataset supera este tamaño, se toma
# una muestra representativa para que RF y MLP terminen en minutos.
# Con el dataset actual (69.064 correos) este límite no se activa.
# Cambia a None para forzar siempre el dataset completo.
SAMPLE_SIZE: int | None = 200_000

# Mismo vectorizador para todos los modelos → comparación justa.
MAX_TFIDF_FEATURES = 20_000


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def load_data(sample_size: int | None = SAMPLE_SIZE) -> pd.DataFrame:
    print(f"\n[Datos] Cargando dataset desde {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH, usecols=["text", "label"])
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str)
    df["label"] = df["label"].astype(int)

    total = len(df)
    if sample_size and total > sample_size:
        print(
            f"[Datos] Dataset completo: {total:,} filas. "
            f"Usando muestra estratificada de {sample_size:,} ejemplos."
        )
        df = df.sample(n=sample_size, random_state=42, stratify=df["label"])
    else:
        print(f"[Datos] Total de ejemplos: {total:,}")

    dist = df["label"].value_counts().sort_index()
    print(f"[Datos] Legítimo (0): {dist.get(0, 0):,} | Phishing (1): {dist.get(1, 0):,}")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Definición de modelos
# ---------------------------------------------------------------------------

def build_classifiers() -> dict:
    """
    Devuelve los cuatro clasificadores a comparar.
    Todos reciben exactamente las mismas features TF-IDF.
    """
    return {
        # ── 1. Regresión Logística ────────────────────────────────────────
        # Modelo lineal clásico. Aprende un peso por cada palabra y los combina
        # para estimar la probabilidad de phishing. Es rápido, interpretable y
        # funciona muy bien con TF-IDF. Actúa como baseline.
        "Regresion_Logistica": LogisticRegression(
            C=1.0,                    # Regularización: evita sobreajuste
            max_iter=1000,
            class_weight="balanced",  # Compensa desbalanceo de clases
            solver="saga",            # Mejor para datasets grandes
            n_jobs=-1,                # Usa todos los núcleos
            random_state=42,
        ),

        # ── 2. SVM Lineal ─────────────────────────────────────────────────
        # Busca el hiperplano que mejor separa phishing de legítimo con el mayor
        # margen posible. LinearSVC es muy rápido. Lo envolvemos con
        # CalibratedClassifierCV para poder obtener probabilidades (la API las
        # necesita). La calibración añade tiempo pero es imprescindible.
        "SVM_Lineal": CalibratedClassifierCV(
            LinearSVC(
                C=1.0,
                class_weight="balanced",
                max_iter=2000,
                random_state=42,
            ),
            cv=3,  # 3 folds de cross-validation para calibrar probabilidades
        ),

        # ── 3. Random Forest ──────────────────────────────────────────────
        # Ensamble de 100 árboles de decisión. Cada árbol se entrena sobre una
        # submuestra aleatoria de los datos y de las features. La predicción
        # final es la votación de todos los árboles. Es robusto al ruido pero
        # más lento que los modelos lineales.
        "Random_Forest": RandomForestClassifier(
            n_estimators=100,         # Número de árboles
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        ),

        # ── 4. Red Neuronal MLP ───────────────────────────────────────────
        # Red de neuronas artificiales con 2 capas ocultas (256 y 128 neuronas).
        # Cada neurona aplica una transformación no lineal (ReLU). Early stopping
        # detiene el entrenamiento cuando el error en validación deja de mejorar,
        # evitando sobreajuste sin fijar un número de épocas a mano.
        "Red_Neuronal_MLP": MLPClassifier(
            hidden_layer_sizes=(256, 128),
            activation="relu",
            solver="adam",            # Optimizador adaptativo, estándar para redes
            max_iter=200,             # Techo suficiente; early_stopping para antes si converge
            early_stopping=True,      # Para cuando no mejora más
            n_iter_no_change=10,      # Más paciencia para evitar paradas prematuras
            validation_fraction=0.1,  # 10% del train para validar
            random_state=42,
            verbose=False,
        ),
    }


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------

def evaluate(clf, X_test, y_test, name: str) -> dict:
    """Calcula todas las métricas relevantes para un clasificador."""
    y_pred = clf.predict(X_test)
    report_dict = classification_report(
        y_test, y_pred, output_dict=True, digits=4, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred).tolist()

    return {
        "modelo": name,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_phishing": float(precision_score(y_test, y_pred, pos_label=1, zero_division=0)),
        "recall_phishing":    float(recall_score(y_test, y_pred,    pos_label=1, zero_division=0)),
        "f1_phishing":        float(f1_score(y_test, y_pred,        pos_label=1, zero_division=0)),
        "precision_legitimo": float(precision_score(y_test, y_pred, pos_label=0, zero_division=0)),
        "recall_legitimo":    float(recall_score(y_test, y_pred,    pos_label=0, zero_division=0)),
        "f1_legitimo":        float(f1_score(y_test, y_pred,        pos_label=0, zero_division=0)),
        "f1_macro":           float(f1_score(y_test, y_pred, average="macro",    zero_division=0)),
        "f1_weighted":        float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
        "confusion_matrix": cm,
        "classification_report": report_dict,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Datos
    df = load_data()
    X, y = df["text"], df["label"]

    # 2. Split estratificado — el mismo para todos los modelos
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\n[Split] Train: {len(X_train):,} | Test: {len(X_test):,}")

    # 3. Preprocesado NLP explícito — se aplica antes del TF-IDF
    #    Tokenización → eliminación de stopwords → lematización/stemming
    print("\n[Preprocesado] Aplicando pipeline NLP (stopwords, lematización) ...")
    preprocessor = TextPreprocessor()
    X_train_clean = preprocessor.fit_transform(X_train)
    X_test_clean  = preprocessor.transform(X_test)
    print("[Preprocesado] Listo.")

    # 4. TF-IDF — ajustado UNA sola vez sobre los datos YA preprocesados
    #    Todos los modelos reciben exactamente las mismas features → comparación justa.
    print(f"\n[TF-IDF] Ajustando vectorizador ({MAX_TFIDF_FEATURES:,} features, bigramas) ...")
    tfidf = TfidfVectorizer(
        lowercase=False,       # Ya está en minúsculas desde el preprocesado
        ngram_range=(1, 2),
        max_features=MAX_TFIDF_FEATURES,
        sublinear_tf=True,
    )
    X_train_vec = tfidf.fit_transform(X_train_clean)
    X_test_vec  = tfidf.transform(X_test_clean)
    print("[TF-IDF] Listo.")

    # 4. Entrenar y evaluar cada clasificador
    classifiers = build_classifiers()
    results: list[dict] = []
    trained_clfs: dict = {}

    for name, clf in classifiers.items():
        print(f"\n{'-' * 60}")
        print(f"  Entrenando: {name}")

        t0 = time.time()
        clf.fit(X_train_vec, y_train)
        elapsed = time.time() - t0
        print(f"  Tiempo de entrenamiento: {elapsed:.1f}s")

        result = evaluate(clf, X_test_vec, y_test, name)
        result["tiempo_entrenamiento_s"] = round(elapsed, 2)
        results.append(result)
        trained_clfs[name] = clf

        print(
            f"  Accuracy:      {result['accuracy']:.4f}\n"
            f"  Precision:     {result['precision_phishing']:.4f}\n"
            f"  Recall:        {result['recall_phishing']:.4f}\n"
            f"  F1 (phishing): {result['f1_phishing']:.4f}\n"
            f"  F1 Macro:      {result['f1_macro']:.4f}"
        )

    # 5. Tabla resumen
    print(f"\n{'=' * 60}")
    print("TABLA COMPARATIVA FINAL")
    print(f"{'=' * 60}")
    summary_rows = [
        {
            "Modelo":            r["modelo"].replace("_", " "),
            "Accuracy":          f"{r['accuracy']:.4f}",
            "Prec. Phishing":    f"{r['precision_phishing']:.4f}",
            "Recall Phishing":   f"{r['recall_phishing']:.4f}",
            "F1 Phishing":       f"{r['f1_phishing']:.4f}",
            "F1 Macro":          f"{r['f1_macro']:.4f}",
            "Tiempo (s)":        r["tiempo_entrenamiento_s"],
        }
        for r in results
    ]
    df_summary = pd.DataFrame(summary_rows)
    print(df_summary.to_string(index=False))

    # 6. Guardar resultados
    RESULTS_DIR.mkdir(exist_ok=True)

    csv_path = RESULTS_DIR / "resultados_modelos.csv"
    df_summary.to_csv(csv_path, index=False)
    print(f"\n[Guardado] Tabla CSV en: {csv_path}")

    json_path = RESULTS_DIR / "resultados_modelos.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"[Guardado] JSON detallado en: {json_path}")

    # 7. Mejor modelo por F1 macro → guardarlo como pipeline completo
    best_result = max(results, key=lambda r: r["f1_macro"])
    best_name   = best_result["modelo"]
    print(f"\n[Mejor modelo] {best_name} — F1 macro = {best_result['f1_macro']:.4f}")

    best_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("tfidf",        tfidf),
        ("clf",          trained_clfs[best_name]),
    ])
    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_pipeline, MODEL_OUTPUT_PATH)
    print(f"[Guardado] Pipeline en: {MODEL_OUTPUT_PATH}")
    print("\n¡Comparativa completada!")


if __name__ == "__main__":
    main()
