"""
visualize.py
============
Genera gráficas de alta calidad (300 DPI) listas para incluir en la memoria
del TFG a partir de los resultados guardados en data/resultados_modelos.json.

Gráficas generadas en la carpeta graficas/
------------------------------------------
  01_comparativa_metricas.png   – Barras agrupadas con las métricas principales
  02_matrices_confusion.png     – Cuatro matrices de confusión en rejilla 2×2
  03_tiempo_entrenamiento.png   – Barras horizontales con el tiempo de entrenamiento

Uso
---
  python -m backend.ml.visualize
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
BASE_DIR     = Path(__file__).resolve().parent.parent.parent
RESULTS_JSON = BASE_DIR / "data" / "resultados_modelos.json"
GRAFICAS_DIR = BASE_DIR / "graficas"

# ---------------------------------------------------------------------------
# Estilo general
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family":     "DejaVu Sans",
    "font.size":       11,
    "axes.titlesize":  13,
    "axes.titleweight":"bold",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "figure.dpi":      150,
    "savefig.dpi":     300,
    "savefig.bbox":    "tight",
})

# Debe coincidir con MAX_TFIDF_FEATURES de compare_models.py
MAX_TFIDF_FEATURES = 20_000

# Colores por modelo (consistentes en todas las gráficas)
COLORES = {
    "Regresion_Logistica": "#4C72B0",   # Azul
    "SVM_Lineal":          "#55A868",   # Verde
    "Random_Forest":       "#DD8452",   # Naranja
    "Red_Neuronal_MLP":    "#C44E52",   # Rojo
}

NOMBRES_BONITOS = {
    "Regresion_Logistica": "Regresión\nLogística",
    "SVM_Lineal":          "SVM\nLineal",
    "Random_Forest":       "Random\nForest",
    "Red_Neuronal_MLP":    "Red Neuronal\nMLP",
}


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def cargar_resultados() -> list[dict]:
    if not RESULTS_JSON.exists():
        raise FileNotFoundError(
            f"No se encontró {RESULTS_JSON}.\n"
            "Ejecuta primero: python -m backend.ml.compare_models"
        )
    with open(RESULTS_JSON, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Gráfica 1 — Comparativa de métricas
# ---------------------------------------------------------------------------

def grafica_comparativa_metricas(resultados: list[dict]) -> None:
    """
    Barras agrupadas mostrando Accuracy, Precision, Recall y F1 (phishing)
    para cada modelo. Facilita la comparación visual de un vistazo.
    """
    metricas = {
        "Accuracy":          [r["accuracy"]           for r in resultados],
        "Precision\n(phishing)": [r["precision_phishing"] for r in resultados],
        "Recall\n(phishing)":    [r["recall_phishing"]    for r in resultados],
        "F1\n(phishing)":        [r["f1_phishing"]         for r in resultados],
        "F1 Macro":          [r["f1_macro"]            for r in resultados],
    }

    modelos   = [r["modelo"] for r in resultados]
    n_modelos = len(modelos)
    n_metricas = len(metricas)

    x      = np.arange(n_metricas)
    ancho  = 0.18
    offset = np.linspace(-(n_modelos - 1) / 2, (n_modelos - 1) / 2, n_modelos) * ancho

    fig, ax = plt.subplots(figsize=(13, 6))

    for i, (modelo, off) in enumerate(zip(modelos, offset)):
        valores = [metricas[m][i] for m in metricas]
        barras  = ax.bar(
            x + off, valores,
            width=ancho,
            color=COLORES[modelo],
            label=NOMBRES_BONITOS[modelo].replace("\n", " "),
            edgecolor="white",
            linewidth=0.5,
        )
        # Etiqueta de valor encima de cada barra
        for barra, val in zip(barras, valores):
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                barra.get_height() + 0.001,
                f"{val:.3f}",
                ha="center", va="bottom",
                fontsize=7.5, color="#333333",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(list(metricas.keys()))
    ax.set_ylim(0.96, 1.005)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.3f}"))
    ax.set_ylabel("Valor de la métrica")
    total_test = sum(sum(fila) for fila in resultados[0]["confusion_matrix"])
    ax.set_title(
        f"Comparativa de métricas por modelo\n"
        f"(test: {total_test:,} correos · TF-IDF {MAX_TFIDF_FEATURES:,} features)"
    )
    ax.legend(
        title="Modelo", loc="lower right",
        framealpha=0.9, fontsize=9,
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    ruta = GRAFICAS_DIR / "01_comparativa_metricas.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"[OK] {ruta}")


# ---------------------------------------------------------------------------
# Gráfica 2 — Matrices de confusión
# ---------------------------------------------------------------------------

def grafica_matrices_confusion(resultados: list[dict]) -> None:
    """
    Rejilla 2×2 con la matriz de confusión de cada modelo representada
    como un mapa de calor. Los valores en la diagonal son los aciertos.
    """
    total_test = sum(sum(fila) for fila in resultados[0]["confusion_matrix"])
    fig, ejes = plt.subplots(2, 2, figsize=(11, 9))
    fig.suptitle(
        f"Matrices de confusión por modelo\n(conjunto de test · {total_test:,} correos)",
        fontsize=14, fontweight="bold", y=1.01,
    )

    etiquetas = ["Legítimo (0)", "Phishing (1)"]

    for ax, resultado in zip(ejes.flat, resultados):
        modelo = resultado["modelo"]
        cm     = np.array(resultado["confusion_matrix"])

        # Normalizar para porcentajes (cada fila suma 1)
        cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

        sns.heatmap(
            cm_norm,
            annot=False,
            fmt=".2%",
            cmap="Blues",
            ax=ax,
            xticklabels=etiquetas,
            yticklabels=etiquetas,
            linewidths=0.5,
            linecolor="white",
            vmin=0, vmax=1,
        )

        # Anotaciones manuales: número absoluto + porcentaje
        for fila in range(2):
            for col in range(2):
                valor_abs  = cm[fila, col]
                valor_pct  = cm_norm[fila, col]
                color_texto = "white" if valor_pct > 0.5 else "#333333"
                ax.text(
                    col + 0.5, fila + 0.5,
                    f"{valor_abs:,}\n({valor_pct:.1%})",
                    ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color=color_texto,
                )

        f1   = resultado["f1_phishing"]
        rec  = resultado["recall_phishing"]
        ax.set_title(
            f"{NOMBRES_BONITOS[modelo].replace(chr(10), ' ')}\n"
            f"F1={f1:.4f}  ·  Recall={rec:.4f}",
            fontsize=10,
        )
        ax.set_xlabel("Predicción")
        ax.set_ylabel("Realidad")

    plt.tight_layout()
    ruta = GRAFICAS_DIR / "02_matrices_confusion.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"[OK] {ruta}")


# ---------------------------------------------------------------------------
# Gráfica 3 — Tiempo de entrenamiento
# ---------------------------------------------------------------------------

def grafica_tiempo_entrenamiento(resultados: list[dict]) -> None:
    """
    Barras horizontales mostrando el tiempo de entrenamiento de cada modelo.
    Útil para argumentar el tradeoff precisión/velocidad en la defensa.
    """
    modelos  = [NOMBRES_BONITOS[r["modelo"]].replace("\n", " ") for r in resultados]
    tiempos  = [r["tiempo_entrenamiento_s"] for r in resultados]
    colores  = [COLORES[r["modelo"]] for r in resultados]

    fig, ax = plt.subplots(figsize=(9, 4))

    barras = ax.barh(modelos, tiempos, color=colores, edgecolor="white", height=0.55)

    # Etiqueta con el tiempo exacto
    for barra, t in zip(barras, tiempos):
        ax.text(
            barra.get_width() + max(tiempos) * 0.01,
            barra.get_y() + barra.get_height() / 2,
            f"{t:.1f} s",
            va="center", fontsize=10,
        )

    ax.set_xlabel("Tiempo de entrenamiento (segundos)")
    total_test = sum(sum(fila) for fila in resultados[0]["confusion_matrix"])
    ax.set_title(
        f"Tiempo de entrenamiento por modelo\n"
        f"(test: {total_test:,} correos · TF-IDF {MAX_TFIDF_FEATURES:,} features)"
    )
    ax.set_xlim(0, max(tiempos) * 1.18)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.invert_yaxis()  # El modelo más rápido queda arriba

    plt.tight_layout()
    ruta = GRAFICAS_DIR / "03_tiempo_entrenamiento.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"[OK] {ruta}")


# ---------------------------------------------------------------------------
# Gráfica 4 — Radar / Spider chart de métricas
# ---------------------------------------------------------------------------

def grafica_radar(resultados: list[dict]) -> None:
    """
    Gráfica de araña (radar chart) que muestra de un vistazo el perfil
    de cada modelo en cinco dimensiones métricas.
    """
    categorias    = ["Accuracy", "Precision\nPhishing", "Recall\nPhishing",
                     "F1 Phishing", "F1 Macro"]
    n_categorias  = len(categorias)
    angulos       = np.linspace(0, 2 * np.pi, n_categorias, endpoint=False).tolist()
    angulos      += angulos[:1]  # Cerrar el polígono

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    for resultado in resultados:
        modelo  = resultado["modelo"]
        valores = [
            resultado["accuracy"],
            resultado["precision_phishing"],
            resultado["recall_phishing"],
            resultado["f1_phishing"],
            resultado["f1_macro"],
        ]
        valores += valores[:1]  # Cerrar el polígono

        ax.plot(angulos, valores, "o-", linewidth=2,
                color=COLORES[modelo],
                label=NOMBRES_BONITOS[modelo].replace("\n", " "))
        ax.fill(angulos, valores, alpha=0.07, color=COLORES[modelo])

    # Escala del eje radial
    ax.set_ylim(0.97, 1.0)
    ax.set_yticks([0.97, 0.98, 0.99, 1.00])
    ax.set_yticklabels(["0.970", "0.980", "0.990", "1.000"], fontsize=8)

    ax.set_xticks(angulos[:-1])
    ax.set_xticklabels(categorias, fontsize=10)
    ax.set_title("Perfil de métricas por modelo\n(radar chart)",
                 fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.5)

    ruta = GRAFICAS_DIR / "04_radar_metricas.png"
    fig.savefig(ruta)
    plt.close(fig)
    print(f"[OK] {ruta}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Cargando resultados desde {RESULTS_JSON} ...")
    resultados = cargar_resultados()
    print(f"Modelos encontrados: {[r['modelo'] for r in resultados]}\n")

    GRAFICAS_DIR.mkdir(exist_ok=True)
    print(f"Generando gráficas en {GRAFICAS_DIR} ...\n")

    grafica_comparativa_metricas(resultados)
    grafica_matrices_confusion(resultados)
    grafica_tiempo_entrenamiento(resultados)
    grafica_radar(resultados)

    print(f"\n¡Listo! Se han generado 4 gráficas en: {GRAFICAS_DIR}")
    print("Inclúyelas en la memoria del TFG con alta resolución (300 DPI).")


if __name__ == "__main__":
    main()
