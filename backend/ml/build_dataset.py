from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

try:
    from datasets import load_dataset
except ImportError:  # pragma: no cover
    load_dataset = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_ceas() -> Optional[pd.DataFrame]:
    """Carga CEAS_08.csv y lo adapta a columnas text/label/lang."""
    path = BASE_DIR / "CEAS_08.csv"
    if not path.exists():
        print(f"[CEAS] No encontrado: {path}")
        return None

    print(f"[CEAS] Cargando {path} ...")
    df = pd.read_csv(path)

    required_cols = {"subject", "body", "label"}
    if not required_cols.issubset(set(df.columns)):
        print(f"[CEAS] Columnas esperadas no encontradas. Encontradas: {list(df.columns)}")
        return None

    df["subject"] = df["subject"].fillna("")
    df["body"] = df["body"].fillna("")
    df_out = pd.DataFrame()
    df_out["text"] = (df["subject"] + " " + df["body"]).str.strip()
    df_out["label"] = df["label"].astype(int)
    df_out["lang"] = "en"

    print(f"[CEAS] Ejemplos cargados: {len(df_out)}")
    return df_out


def load_enron() -> Optional[pd.DataFrame]:
    """Carga Enron.csv y lo adapta a columnas text/label/lang."""
    path = BASE_DIR / "Enron.csv"
    if not path.exists():
        print(f"[Enron] No encontrado: {path}")
        return None

    print(f"[Enron] Cargando {path} ...")
    df = pd.read_csv(path)

    required_cols = {"subject", "body", "label"}
    if not required_cols.issubset(set(df.columns)):
        print(f"[Enron] Columnas esperadas no encontradas. Encontradas: {list(df.columns)}")
        return None

    df["subject"] = df["subject"].fillna("")
    df["body"] = df["body"].fillna("")
    df_out = pd.DataFrame()
    df_out["text"] = (df["subject"] + " " + df["body"]).str.strip()
    df_out["label"] = df["label"].astype(int)
    df_out["lang"] = "en"

    print(f"[Enron] Ejemplos cargados: {len(df_out)}")
    return df_out


def load_spamspa() -> Optional[pd.DataFrame]:
    """
    Descarga el dataset de spam en español 'Gabrielaz/spamspa' desde HuggingFace
    y lo adapta a columnas text/label/lang.
    """
    if load_dataset is None:
        print("[SpamSPA] La librería 'datasets' no está instalada. Ejecuta 'pip install datasets'.")
        return None

    print("[SpamSPA] Descargando dataset 'Gabrielaz/spamspa' desde HuggingFace ...")
    try:
        ds = load_dataset("Gabrielaz/spamspa")
    except Exception as exc:  # pragma: no cover
        print(f"[SpamSPA] Error al descargar el dataset: {exc}")
        return None

    frames: List[pd.DataFrame] = []
    for split_name, split in ds.items():
        print(f"[SpamSPA] Convirtiendo split '{split_name}' a pandas ...")
        df_split = split.to_pandas()
        frames.append(df_split)

    df = pd.concat(frames, ignore_index=True)

    # El dataset está documentado con columnas 'text' y 'label'
    if "text" not in df.columns or "label" not in df.columns:
        print(f"[SpamSPA] Columnas esperadas 'text' y 'label' no encontradas. Encontradas: {list(df.columns)}")
        return None

    df_out = pd.DataFrame()
    df_out["text"] = df["text"].astype(str)
    df_out["label"] = df["label"].astype(int)
    df_out["lang"] = "es"

    print(f"[SpamSPA] Ejemplos cargados: {len(df_out)}")
    return df_out


def load_manual_es_legit() -> Optional[pd.DataFrame]:
    """
    Carga ejemplos manuales de correos legítimos en español, si existen.

    Espera un CSV en 'data/manual_es_legit.csv' con al menos una columna:
    - text: contenido completo del correo.
    La etiqueta se asume 0 (legítimo).
    """
    path = BASE_DIR / "data" / "manual_es_legit.csv"
    if not path.exists():
        return None

    print(f"[ES manual] Cargando ejemplos legítimos en español desde {path} ...")
    df = pd.read_csv(path)
    if "text" not in df.columns:
        print(f"[ES manual] No se ha encontrado la columna 'text' en {path}. Columnas: {list(df.columns)}")
        return None

    df_out = pd.DataFrame()
    df_out["text"] = df["text"].astype(str)
    df_out["label"] = 0
    df_out["lang"] = "es"

    print(f"[ES manual] Ejemplos cargados: {len(df_out)}")
    return df_out


def load_manual_es_phishing() -> Optional[pd.DataFrame]:
    """
    Carga ejemplos manuales de correos de phishing en español, si existen.

    Espera un CSV en 'data/manual_es_phishing.csv' con al menos una columna:
    - text: contenido completo del correo.
    La etiqueta se asume 1 (phishing).
    """
    path = BASE_DIR / "data" / "manual_es_phishing.csv"
    if not path.exists():
        return None

    print(f"[ES phishing manual] Cargando ejemplos de phishing en español desde {path} ...")
    df = pd.read_csv(path)
    if "text" not in df.columns:
        print(
            f"[ES phishing manual] No se ha encontrado la columna 'text' en {path}. "
            f"Columnas: {list(df.columns)}"
        )
        return None

    df_out = pd.DataFrame()
    df_out["text"] = df["text"].astype(str)
    df_out["label"] = 1
    df_out["lang"] = "es"

    print(f"[ES phishing manual] Ejemplos cargados: {len(df_out)}")
    return df_out


def main():
    print(f"Base del proyecto: {BASE_DIR}")

    ceas = load_ceas()
    enron = load_enron()
    spamspa = load_spamspa()
    manual_es = load_manual_es_legit()
    manual_es_phish = load_manual_es_phishing()

    dfs = [d for d in [ceas, enron, spamspa, manual_es, manual_es_phish] if d is not None]
    if not dfs:
        raise SystemExit("No se ha podido cargar ningún dataset. Revisa rutas y dependencias.")

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"Total de ejemplos combinados: {len(df_all)}")

    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / "emails.csv"

    df_all.to_csv(output_path, index=False)
    print(f"Dataset combinado guardado en: {output_path}")


if __name__ == "__main__":
    main()

