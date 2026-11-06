# ── Imagen base ───────────────────────────────────────────────────────────────
# Python 3.11 slim: versión ligera sin herramientas de compilación innecesarias
FROM python:3.11-slim

# ── Directorio de trabajo dentro del contenedor ───────────────────────────────
WORKDIR /app

# ── Instalar dependencias ─────────────────────────────────────────────────────
# Copiamos requirements.txt primero para aprovechar la caché de capas:
# si el código cambia pero las dependencias no, no se reinstala todo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Descargar recursos NLTK ───────────────────────────────────────────────────
# wordnet y omw-1.4 son necesarios para la lematización en inglés.
# Se descargan en tiempo de build para que no fallen al arrancar el servidor.
RUN python -m nltk.downloader wordnet omw-1.4

# ── Copiar el código del proyecto ─────────────────────────────────────────────
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY graficas/ ./graficas/
COPY data/     ./data/

# ── Puerto expuesto ───────────────────────────────────────────────────────────
EXPOSE 8000

# ── Comando de arranque ───────────────────────────────────────────────────────
# --host 0.0.0.0: acepta conexiones desde fuera del contenedor
# --workers 1:    un solo proceso (el modelo joblib no es thread-safe con más)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
