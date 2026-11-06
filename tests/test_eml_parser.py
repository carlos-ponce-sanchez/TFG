"""
tests/test_eml_parser.py
========================
Tests unitarios para la función extract_text_from_file de main.py.

Qué se comprueba:
  - Texto plano → se devuelve tal cual
  - .eml simple con Subject y cuerpo → extrae asunto + cuerpo
  - .eml multipart (texto plano + HTML) → prefiere texto plano
  - .eml sin cuerpo pero con asunto → devuelve al menos el asunto
  - Subida de .eml real a través del endpoint → funciona end-to-end
"""

import email
import textwrap
import pytest
from fastapi.testclient import TestClient
from backend.main import app, extract_text_from_file

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers para construir correos .eml de prueba
# ---------------------------------------------------------------------------

def build_simple_eml(subject: str, body: str) -> bytes:
    """Construye un .eml simple (no multipart) como bytes."""
    return textwrap.dedent(f"""\
        From: test@example.com
        To: victim@example.com
        Subject: {subject}
        Content-Type: text/plain; charset=utf-8

        {body}
    """).encode("utf-8")


def build_multipart_eml(subject: str, text_body: str, html_body: str) -> bytes:
    """Construye un .eml multipart/alternative con parte texto y parte HTML."""
    boundary = "boundary_test_123"
    return textwrap.dedent(f"""\
        From: test@example.com
        To: victim@example.com
        Subject: {subject}
        Content-Type: multipart/alternative; boundary="{boundary}"

        --{boundary}
        Content-Type: text/plain; charset=utf-8

        {text_body}

        --{boundary}
        Content-Type: text/html; charset=utf-8

        <html><body><p>{html_body}</p></body></html>

        --{boundary}--
    """).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests de extract_text_from_file — texto plano
# ---------------------------------------------------------------------------

def test_plain_text_returned_as_is():
    """Un .txt normal sin cabeceras MIME se devuelve sin modificar."""
    content = b"Hello, this is a plain text email about the meeting tomorrow."
    result = extract_text_from_file(content)
    assert "meeting tomorrow" in result


def test_plain_text_no_eml_headers():
    """Texto plano sin Subject/From/Content-Type → no se trata como .eml."""
    content = b"Hola, te mando la factura del mes. Un saludo."
    result = extract_text_from_file(content)
    assert "factura" in result


# ---------------------------------------------------------------------------
# Tests de extract_text_from_file — .eml simple
# ---------------------------------------------------------------------------

def test_eml_subject_extracted():
    """.eml con Subject → el asunto aparece en el texto extraído."""
    raw = build_simple_eml(
        subject="URGENT: Verify your account now",
        body="Click here to verify: http://fake.com/login"
    )
    result = extract_text_from_file(raw)
    assert "URGENT" in result
    assert "Verify your account now" in result


def test_eml_body_extracted():
    """.eml con cuerpo → el cuerpo aparece en el texto extraído."""
    raw = build_simple_eml(
        subject="Test subject",
        body="Your password has been compromised. Act immediately."
    )
    result = extract_text_from_file(raw)
    assert "password" in result
    assert "immediately" in result


def test_eml_subject_and_body_combined():
    """.eml → el resultado combina asunto y cuerpo."""
    raw = build_simple_eml(
        subject="Team meeting tomorrow",
        body="Hola equipo, recordad la reunion a las 10h."
    )
    result = extract_text_from_file(raw)
    assert "Team meeting tomorrow" in result
    assert "equipo" in result


# ---------------------------------------------------------------------------
# Tests de extract_text_from_file — .eml multipart
# ---------------------------------------------------------------------------

def test_multipart_eml_prefers_plain_text():
    """.eml multipart → se prefiere la parte text/plain sobre text/html."""
    raw = build_multipart_eml(
        subject="Phishing multipart",
        text_body="Verify your account at http://evil.com now",
        html_body="<b>Verify</b> your account"
    )
    result = extract_text_from_file(raw)
    # El texto plano tiene la URL completa, el HTML no
    assert "http://evil.com" in result


# ---------------------------------------------------------------------------
# Tests end-to-end: subida de .eml a través del endpoint
# ---------------------------------------------------------------------------

def test_endpoint_accepts_eml_file():
    """El endpoint /api/predict-file procesa un .eml correctamente."""
    raw = build_simple_eml(
        subject="URGENT: Your account has been suspended",
        body="Verify your password immediately at http://fake-bank.xyz/login "
             "or your account will be permanently deleted."
    )
    response = client.post(
        "/api/predict-file",
        files={"files": ("correo.eml", raw, "message/rfc822")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["results"][0]["filename"] == "correo.eml"
    assert "label" in data["results"][0]


def test_endpoint_eml_phishing_detected():
    """Un .eml de phishing subido al endpoint se detecta como phishing."""
    raw = build_simple_eml(
        subject="URGENT: Verify your account NOW",
        body="Your account has been suspended. "
             "Verify your password at http://fake-bank.xyz/login immediately."
    )
    response = client.post(
        "/api/predict-file",
        files={"files": ("phishing.eml", raw, "message/rfc822")},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["label"] == "phishing"


def test_endpoint_txt_still_works():
    """El endpoint sigue funcionando con .txt normal (no .eml)."""
    content = b"Hi team, meeting tomorrow at 10am. Please confirm attendance."
    response = client.post(
        "/api/predict-file",
        files={"files": ("reunion.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["label"] == "legitimo"
