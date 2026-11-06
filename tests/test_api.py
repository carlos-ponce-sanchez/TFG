"""
tests/test_api.py
=================
Tests de integración para los endpoints de la API FastAPI.
Usa TestClient de FastAPI (basado en httpx) para hacer peticiones reales
al servidor sin necesidad de levantarlo manualmente.

Qué se comprueba:
  - POST /api/predict-text: texto vacío (400), phishing EN, legítimo EN,
    phishing ES, estructura de respuesta, regla de correo corto
  - POST /api/predict-file: subida de archivo, múltiples archivos
"""

import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app


# El TestClient carga la app completa (modelo incluido) una sola vez
client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/predict-text — validaciones básicas
# ---------------------------------------------------------------------------

def test_empty_text_returns_400():
    response = client.post("/api/predict-text", json={"text": ""})
    assert response.status_code == 400


def test_whitespace_only_returns_400():
    response = client.post("/api/predict-text", json={"text": "   "})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/predict-text — estructura de respuesta
# ---------------------------------------------------------------------------

def test_response_has_required_fields():
    response = client.post(
        "/api/predict-text",
        json={"text": "Test email content here to check the response structure"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "label" in data
    assert "score" in data
    assert "features" in data
    assert "top_tokens" in data


def test_label_is_valid_value():
    response = client.post(
        "/api/predict-text",
        json={"text": "Test email content here"},
    )
    assert response.json()["label"] in ("phishing", "legitimo")


def test_score_is_between_0_and_1():
    response = client.post(
        "/api/predict-text",
        json={"text": "Please verify your account now"},
    )
    score = response.json()["score"]
    assert 0.0 <= score <= 1.0


def test_features_has_expected_keys():
    response = client.post(
        "/api/predict-text",
        json={"text": "Visit http://bank.com to verify your account"},
    )
    features = response.json()["features"]
    assert "num_urls" in features
    assert "domains" in features
    assert "urgent_words" in features
    assert "num_chars" in features
    assert "detected_lang" in features


# ---------------------------------------------------------------------------
# POST /api/predict-text — detección de phishing
# ---------------------------------------------------------------------------

def test_phishing_english_detected():
    phishing = (
        "URGENT: Your account has been suspended. "
        "Verify your password immediately at http://fake-bank.xyz/login "
        "or your account will be permanently deleted."
    )
    response = client.post("/api/predict-text", json={"text": phishing})
    assert response.status_code == 200
    assert response.json()["label"] == "phishing"


def test_phishing_spanish_detected():
    phishing = (
        "URGENTE: Su cuenta bancaria ha sido bloqueada. "
        "Verifique sus datos en http://banco-seguro-falso.es/login "
        "o perderá el acceso permanentemente."
    )
    response = client.post("/api/predict-text", json={"text": phishing})
    assert response.status_code == 200
    assert response.json()["label"] == "phishing"


# ---------------------------------------------------------------------------
# POST /api/predict-text — detección de correo legítimo
# ---------------------------------------------------------------------------

def test_legitimate_english_detected():
    legit = (
        "Hi team, the project meeting is scheduled for tomorrow at 10am. "
        "Please confirm your attendance. Best regards."
    )
    response = client.post("/api/predict-text", json={"text": legit})
    assert response.status_code == 200
    assert response.json()["label"] == "legitimo"


# ---------------------------------------------------------------------------
# POST /api/predict-text — regla de correo corto
# ---------------------------------------------------------------------------

def test_short_email_without_urls_is_legitimate():
    # Correos muy cortos sin URLs ni palabras urgentes → legítimo por heurística
    response = client.post("/api/predict-text", json={"text": "Hi, thanks!"})
    assert response.status_code == 200
    assert response.json()["label"] == "legitimo"


def test_short_email_score_capped():
    # La puntuación de un correo corto y seguro debe ser baja (≤ 0.2)
    response = client.post("/api/predict-text", json={"text": "Hi, thanks!"})
    assert response.json()["score"] <= 0.2


# ---------------------------------------------------------------------------
# POST /api/predict-text — idioma detectado
# ---------------------------------------------------------------------------

def test_detected_lang_english():
    text = "Dear user, please verify your account and click here immediately."
    response = client.post("/api/predict-text", json={"text": text})
    assert response.json()["features"]["detected_lang"] == "en"


def test_detected_lang_spanish():
    text = "Estimado usuario, hola, adjunto encontrará su factura mensual. Gracias."
    response = client.post("/api/predict-text", json={"text": text})
    assert response.json()["features"]["detected_lang"] == "es"


# ---------------------------------------------------------------------------
# POST /api/predict-file — subida de archivos
# ---------------------------------------------------------------------------

def test_predict_file_single_upload():
    content = b"URGENT: Verify your account at http://evil.com/login immediately"
    response = client.post(
        "/api/predict-file",
        files={"files": ("correo.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["filename"] == "correo.txt"
    assert "label" in data["results"][0]


def test_predict_file_multiple_uploads():
    files = [
        ("files", ("phishing.txt", b"Verify your password at http://fake.com now", "text/plain")),
        ("files", ("legit.txt", b"Hi, meeting tomorrow at 10am. See you there.", "text/plain")),
    ]
    response = client.post("/api/predict-file", files=files)
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    filenames = [r["filename"] for r in results]
    assert "phishing.txt" in filenames
    assert "legit.txt" in filenames


# ---------------------------------------------------------------------------
# POST /api/feedback — valoración del usuario
# ---------------------------------------------------------------------------

def test_feedback_correct_prediction():
    response = client.post("/api/feedback", json={
        "text": "Dear user, verify your account at http://evil.com immediately",
        "predicted_label": "phishing",
        "correct": True,
        "true_label": None,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_feedback_incorrect_prediction():
    response = client.post("/api/feedback", json={
        "text": "Hola equipo, adjunto la factura del mes. Un saludo.",
        "predicted_label": "phishing",
        "correct": False,
        "true_label": "legitimo",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_feedback_invalid_label_returns_400():
    response = client.post("/api/feedback", json={
        "text": "Cualquier correo.",
        "predicted_label": "spam",  # valor inválido
        "correct": True,
    })
    assert response.status_code == 400


def test_feedback_creates_file(tmp_path, monkeypatch):
    """El feedback se guarda en el archivo JSONL."""
    import backend.main as main_mod
    import importlib, json

    feedback_path = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(main_mod, "FEEDBACK_FILE", feedback_path)

    client.post("/api/feedback", json={
        "text": "Test feedback entry.",
        "predicted_label": "legitimo",
        "correct": True,
    })

    assert feedback_path.exists()
    lines = feedback_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["predicted_label"] == "legitimo"
    assert entry["correct"] is True


# ---------------------------------------------------------------------------
# Autenticación por API Key
# ---------------------------------------------------------------------------

def test_no_api_key_allowed_when_no_keys_configured(monkeypatch):
    """Sin API_KEYS configurada, todos los requests pasan (modo desarrollo)."""
    monkeypatch.setattr("backend.main.VALID_API_KEYS", set())
    response = client.post("/api/predict-text", json={"text": "Hello, please verify your account."})
    assert response.status_code == 200


def test_valid_api_key_accepted(monkeypatch):
    """Una clave válida en la cabecera X-API-Key permite el acceso."""
    monkeypatch.setattr("backend.main.VALID_API_KEYS", {"clave-test-123"})
    response = client.post(
        "/api/predict-text",
        json={"text": "Hello, please verify your account."},
        headers={"X-API-Key": "clave-test-123"},
    )
    assert response.status_code == 200


def test_invalid_api_key_rejected(monkeypatch):
    """Una clave inválida devuelve 401 Unauthorized."""
    monkeypatch.setattr("backend.main.VALID_API_KEYS", {"clave-test-123"})
    response = client.post(
        "/api/predict-text",
        json={"text": "Hello, please verify your account."},
        headers={"X-API-Key": "clave-incorrecta"},
    )
    assert response.status_code == 401


def test_missing_api_key_rejected(monkeypatch):
    """Sin cabecera X-API-Key cuando hay claves configuradas devuelve 401."""
    monkeypatch.setattr("backend.main.VALID_API_KEYS", {"clave-test-123"})
    response = client.post(
        "/api/predict-text",
        json={"text": "Hello, please verify your account."},
    )
    assert response.status_code == 401


def test_metrics_endpoint_public(monkeypatch):
    """El endpoint /api/metrics no requiere API key."""
    monkeypatch.setattr("backend.main.VALID_API_KEYS", {"clave-test-123"})
    response = client.get("/api/metrics")
    assert response.status_code == 200
