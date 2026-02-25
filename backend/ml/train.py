from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = BASE_DIR / "data" / "emails.csv"
MODEL_OUTPUT_PATH = Path(__file__).resolve().parent / "phishing_model.joblib"


def load_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"No se ha encontrado el dataset en {DATA_PATH}. "
            "Crea un 'data/emails.csv' con columnas 'text' y 'label'."
        )
    df = pd.read_csv(DATA_PATH)
    if "text" not in df.columns or "label" not in df.columns:
        raise ValueError("El CSV debe contener columnas 'text' y 'label'.")
    return df


def build_pipeline() -> Pipeline:
    tfidf = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=50000,
        sublinear_tf=True,
    )

    clf = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        n_jobs=-1,
    )

    pipeline = Pipeline(
        steps=[
            ("tfidf", tfidf),
            ("clf", clf),
        ]
    )
    return pipeline


def main():
    print(f"Cargando dataset de {DATA_PATH} ...")
    df = load_dataset()

    X = df["text"].astype(str)
    y = df["label"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = build_pipeline()

    print("Entrenando modelo TF-IDF + Regresión Logística...")
    pipeline.fit(X_train, y_train)

    print("Evaluando en conjunto de test...")
    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, digits=4)
    print(report)

    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    print(f"Modelo guardado en: {MODEL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()

