import email
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.ml.predict import load_model, analyze_email_text


BASE_DIR = Path(__file__).resolve().parent.parent

# ── Logging estructurado ──────────────────────────────────────────────────────
# Formato JSON: cada línea de log es un objeto JSON parseable por herramientas
# como Elasticsearch, Datadog o simplemente grep/jq en la terminal.

class JsonFormatter(logging.Formatter):
    """Formateador que emite cada log como una línea JSON."""
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Campos extra añadidos con logger.info("...", extra={...})
        for key in ("endpoint", "label", "score", "lang", "duration_ms",
                    "uploaded_file", "ip", "num_files"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger = logging.getLogger("phishing_api")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False  # Evita duplicados con el logger raíz de uvicorn

# ─────────────────────────────────────────────────────────────────────────────


def extract_text_from_file(raw: bytes) -> str:
    """
    Extrae el texto analizable de un archivo subido.

    Detecta automáticamente el formato por magic bytes (primeros bytes del
    archivo) y aplica el parser correspondiente:
      - PDF  → PyMuPDF  (magic bytes: %PDF)
      - DOCX → python-docx (magic bytes: PK — es un ZIP)
      - EML  → módulo email de la librería estándar (cabeceras MIME)
      - TXT  → decodificación UTF-8 directa
    """
    # ── PDF: empieza con los bytes %PDF ───────────────────────────────────────
    if raw[:4] == b"%PDF":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=raw, filetype="pdf")
            pages_text = [page.get_text() for page in doc]
            return "\n".join(pages_text).strip()
        except Exception:
            pass  # Si falla el parser PDF, caemos al fallback de texto plano

    # ── DOCX: los archivos .docx son ZIPs (magic bytes PK) ───────────────────
    if raw[:2] == b"PK":
        try:
            import docx
            doc = docx.Document(io.BytesIO(raw))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs).strip()
        except Exception:
            pass  # Si falla el parser DOCX, caemos al fallback de texto plano

    # ── EML / TXT: detección por cabeceras MIME ───────────────────────────────
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return raw.decode("utf-8", errors="ignore")

    # Detectamos si es un .eml real comprobando cabeceras típicas de correo
    is_eml = any(msg.get(h) for h in ("Subject", "From", "To", "Content-Type"))

    if not is_eml:
        # Sin cabeceras MIME → texto plano normal
        return raw.decode("utf-8", errors="ignore")

    # ── Extraer asunto ────────────────────────────────────────────────────────
    subject = msg.get("Subject", "")

    # ── Extraer cuerpo ────────────────────────────────────────────────────────
    body_parts = []

    if msg.is_multipart():
        # Correo con varias partes (ej. texto plano + HTML + adjuntos)
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get("Content-Disposition", "")

            # Solo nos interesan las partes de texto, no los adjuntos
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode(charset, errors="ignore"))
            elif content_type == "text/html" and not body_parts:
                # Usamos HTML solo si no hay texto plano disponible
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    # Eliminamos etiquetas HTML básicas para quedarnos con el texto
                    import re
                    html = payload.decode(charset, errors="ignore")
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    body_parts.append(text)
    else:
        # Correo simple sin partes múltiples
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="ignore"))

    body = "\n".join(body_parts).strip()

    # Combinamos asunto y cuerpo igual que hace build_dataset.py con los CSV
    if subject and body:
        return f"{subject}\n\n{body}"
    return subject or body or raw.decode("utf-8", errors="ignore")


def extract_eml_headers(raw: bytes) -> dict | None:
    """
    Extrae y analiza las cabeceras de un archivo .eml.
    Devuelve None si el archivo no es un EML válido.

    Cabeceras extraídas:
      - From, Reply-To, Return-Path: identidad del remitente
      - Subject: asunto del correo

    Señales de alerta detectadas:
      - Reply-To distinto al dominio de From (técnica clásica de phishing:
        el correo parece venir de un sitio legítimo pero las respuestas van
        a una dirección controlada por el atacante)
    """
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return None

    from_header    = msg.get("From", "") or ""
    reply_to       = msg.get("Reply-To", "") or ""
    return_path    = msg.get("Return-Path", "") or ""
    subject        = msg.get("Subject", "") or ""

    # Extrae solo el dominio de una dirección de correo (parte tras el @)
    def _domain(addr: str) -> str:
        match = re.search(r"@([\w.\-]+)", addr)
        return match.group(1).lower() if match else ""

    warnings = []
    from_domain    = _domain(from_header)
    replyto_domain = _domain(reply_to)

    if reply_to and from_domain and replyto_domain and from_domain != replyto_domain:
        warnings.append(
            f"Reply-To ({replyto_domain}) difiere del dominio del remitente ({from_domain})"
        )

    is_eml = any(msg.get(h) for h in ("Subject", "From", "To", "Content-Type"))
    if not is_eml:
        return None

    return {
        "from":        from_header,
        "reply_to":    reply_to or None,
        "return_path": return_path or None,
        "subject":     subject,
        "warnings":    warnings,
    }


FRONTEND_DIR = BASE_DIR / "frontend"
GRAFICAS_DIR = BASE_DIR / "graficas"
METRICS_FILE = BASE_DIR / "data" / "resultados_modelos.json"
FEEDBACK_FILE = BASE_DIR / "data" / "feedback.jsonl"


class TextRequest(BaseModel):
    text: str


class FeedbackRequest(BaseModel):
    text: str
    predicted_label: str   # "phishing" | "legitimo"
    correct: bool          # True si la predicción fue correcta
    true_label: str | None = None  # si correct=False, la etiqueta real


# ── Autenticación por API Key ─────────────────────────────────────────────────
# Las claves válidas se leen de la variable de entorno API_KEYS (separadas por
# comas). Si la variable no está definida, el sistema funciona en modo abierto
# (desarrollo local). En producción corporativa se configuran las claves reales.
#
# Ejemplo de configuración:
#   export API_KEYS="clave-empresa-a,clave-empresa-b"
#
# El cliente debe incluir la cabecera en cada petición:
#   X-API-Key: clave-empresa-a

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def _load_api_keys() -> set:
    raw = os.environ.get("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}

VALID_API_KEYS: set = _load_api_keys()


async def verify_api_key(api_key: str | None = Security(_api_key_header)):
    """
    Dependencia de FastAPI que verifica la API key en cada petición protegida.

    - Si API_KEYS no está configurada (desarrollo local): permite todo.
    - Si API_KEYS está configurada: exige una clave válida en la cabecera
      X-API-Key. Si la clave no es válida devuelve 401 Unauthorized.
    """
    if not VALID_API_KEYS:
        return  # Modo desarrollo: sin restricciones
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Detector de Phishing (EN/ES)")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


model_pipeline = load_model()


@app.post("/api/predict-text")
@limiter.limit("30/minute")
async def predict_text(request: Request, payload: TextRequest, _: None = Security(verify_api_key)):
    t0 = time.perf_counter()
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto del correo no puede estar vacío.")

    result = analyze_email_text(model_pipeline, text)

    logger.info(
        "predict-text",
        extra={
            "endpoint": "/api/predict-text",
            "ip": request.client.host,
            "label": result.get("label"),
            "score": round(result.get("score", 0), 4),
            "lang": result.get("features", {}).get("detected_lang"),
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    )
    return result


@app.post("/api/predict-file")
@limiter.limit("20/minute")
async def predict_file(request: Request, files: List[UploadFile] = File(...), _: None = Security(verify_api_key)):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un fichero.")

    analyses = []
    for f in files:
        t0 = time.perf_counter()
        raw = await f.read()
        try:
            text = extract_text_from_file(raw)
        except Exception:
            raise HTTPException(status_code=400, detail=f"No se ha podido leer el fichero: {f.filename}")

        if not text.strip():
            raise HTTPException(status_code=400, detail=f"El fichero '{f.filename}' está vacío o no contiene texto.")

        analysis = analyze_email_text(model_pipeline, text)

        # Análisis de cabeceras solo para archivos EML
        headers = extract_eml_headers(raw)
        if headers:
            analysis["headers"] = headers

        analyses.append({"filename": f.filename, **analysis})

        logger.info(
            "predict-file",
            extra={
                "endpoint": "/api/predict-file",
                "ip": request.client.host,
                "uploaded_file": f.filename,
                "label": analysis.get("label"),
                "score": round(analysis.get("score", 0), 4),
                "lang": analysis.get("features", {}).get("detected_lang"),
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        )

    return {"results": analyses}


@app.get("/api/metrics")
@limiter.limit("60/minute")
async def get_metrics(request: Request):
    if not METRICS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Archivo de métricas no encontrado. Ejecuta primero: python -m backend.ml.compare_models",
        )
    with open(METRICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # El modelo activo es el que tiene mayor F1 macro en la comparativa
    active_model = max(data, key=lambda m: m["f1_macro"])["modelo"]
    logger.info("get-metrics", extra={"endpoint": "/api/metrics", "ip": request.client.host})
    return {"models": data, "active_model": active_model}


@app.post("/api/feedback")
@limiter.limit("30/minute")
async def post_feedback(request: Request, payload: FeedbackRequest, _: None = Security(verify_api_key)):
    """
    Recibe la valoración del usuario sobre una predicción.

    Guarda cada entrada en `data/feedback.jsonl` (una línea JSON por registro).
    Este archivo puede usarse más adelante para reentrenar el modelo con
    ejemplos marcados como incorrectos — es el bucle de mejora continua
    (active learning).

    Campos guardados:
      - timestamp: cuándo se envió el feedback
      - text: el correo analizado (primeros 500 caracteres para no crecer indefinidamente)
      - predicted_label: lo que dijo el modelo
      - correct: si el usuario considera que fue correcta
      - true_label: si correct=False, la etiqueta que debería haber dado el modelo
      - ip: IP del cliente (para detectar spam de feedback)
    """
    if payload.predicted_label not in ("phishing", "legitimo"):
        raise HTTPException(status_code=400, detail="predicted_label debe ser 'phishing' o 'legitimo'.")
    if not payload.correct and payload.true_label not in ("phishing", "legitimo", None):
        raise HTTPException(status_code=400, detail="true_label debe ser 'phishing' o 'legitimo'.")

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "text_snippet": payload.text[:500],  # solo primeros 500 chars
        "predicted_label": payload.predicted_label,
        "correct": payload.correct,
        "true_label": payload.true_label if not payload.correct else payload.predicted_label,
        "ip": request.client.host,
    }

    # Añadir al archivo JSONL (una línea por entrada, append-safe)
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info(
        "feedback",
        extra={
            "endpoint": "/api/feedback",
            "ip": request.client.host,
            "label": payload.predicted_label,
            "correct": payload.correct,
        },
    )
    return {"status": "ok", "message": "Feedback registrado. Gracias por ayudar a mejorar el sistema."}


if GRAFICAS_DIR.exists():
    app.mount("/graficas", StaticFiles(directory=str(GRAFICAS_DIR)), name="graficas")

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
