# Detector de Phishing (Inglés y Español)

Este proyecto implementa un sistema completo para detectar correos de phishing tanto en inglés como en español. Incluye:

- Un **modelo de aprendizaje automático** (baseline con TF-IDF + Regresión Logística).
- Un **backend en FastAPI** que expone endpoints para analizar texto y ficheros.
- Una **interfaz web** con caja de texto y zona de *drag & drop* que muestra el resultado (phishing / legítimo) y estadísticas explicativas.

## Estructura del proyecto

- `backend/`
  - `main.py`: aplicación FastAPI con endpoints para predicción.
  - `ml/`
    - `build_dataset.py`: script para combinar datasets (inglés + español) en un único CSV.
    - `train.py`: script para entrenar el modelo.
    - `predict.py`: utilidades para cargar el modelo y generar predicciones y explicaciones.
- `frontend/`
  - `index.html`, `styles.css`, `app.js`: interfaz web.
- `data/`
  - `emails.csv`: dataset de entrenamiento (no incluido por defecto).
- `requirements.txt`: dependencias de Python.

## Dataset esperado

El script de entrenamiento (`backend/ml/train.py`) espera un fichero CSV en `data/emails.csv` con al menos las siguientes columnas:

- `text`: texto completo del correo (asunto + cuerpo).
- `label`: `1` para phishing y `0` para correo legítimo.
- `lang` (opcional): idioma (`"en"` o `"es"`), útil para análisis por idioma.

Puedes adaptar fácilmente el script si tus columnas tienen otros nombres.

## Cómo instalar y ejecutar

1. Crear y activar un entorno virtual (recomendado).
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Construir el dataset combinado (inglés + español). Asegúrate de haber descargado previamente en la raíz del proyecto:

- `CEAS_08.csv`
- `Enron.csv`

Luego ejecuta:

```bash
python -m backend.ml.build_dataset
```

Esto generará `data/emails.csv`.

Opcionalmente, puedes añadir tus propios correos legítimos en español creando un
fichero `data/manual_es_legit.csv` con una columna `text` (una fila por correo).
El script `build_dataset.py` los incorporará automáticamente como ejemplos `label = 0`
para reducir falsos positivos en español.

Del mismo modo, puedes añadir ejemplos manuales de correos de phishing en español
en `data/manual_es_phishing.csv` (columna `text`), que se incorporarán como
`label = 1` para mejorar la detección de phishing en este idioma.

4. Entrenar el modelo:

```bash
python -m backend.ml.train
```

Esto generará un fichero `phishing_model.joblib` dentro de `backend/ml/`.

5. Lanzar el servidor FastAPI:

```bash
uvicorn backend.main:app --reload
```

5. Abrir la interfaz web:

- Si se sirve como estático desde FastAPI, accede a `http://localhost:8000/`.
- Alternativamente, abre `frontend/index.html` directamente en el navegador (en ese caso ajusta las URLs de la API si es necesario).

## Notas para el TFG

- Puedes extender el modelo baseline con un modelo basado en *transformers* multilingüe para mejorar el rendimiento.
- Incluye en la memoria del TFG:
  - Descripción del dataset y del preprocesado.
  - Comparación de modelos (baseline vs avanzado).
  - Métricas de evaluación (precision, recall, F1, etc.).
  - Capturas de pantalla de la interfaz web y ejemplos de explicaciones.

