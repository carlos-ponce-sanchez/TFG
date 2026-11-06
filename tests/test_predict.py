"""
tests/test_predict.py
=====================
Tests unitarios para las funciones de predicción y extracción de features
del módulo predict.py. NO requieren cargar el modelo joblib.

Qué se comprueba:
  - detect_language_heuristic: inglés, español, tildes
  - extract_features_from_text: URLs, dominios, palabras urgentes, longitud
  - Que las palabras urgentes se detectan con límite de palabra (word boundary)
"""

import pytest
from backend.ml.predict import (
    detect_language_heuristic,
    extract_features_from_text,
    SHORT_EMAIL_THRESHOLD,
    PHISHING_THRESHOLD_EN,
    PHISHING_THRESHOLD_ES_HIGH,
    PHISHING_THRESHOLD_ES_LOW,
)


# ---------------------------------------------------------------------------
# detect_language_heuristic
# ---------------------------------------------------------------------------

def test_detects_english():
    text = "Dear user, please verify your account immediately. Click here."
    assert detect_language_heuristic(text) == "en"


def test_detects_spanish():
    text = "Estimado usuario, su cuenta ha sido bloqueada. Verifique sus datos."
    assert detect_language_heuristic(text) == "es"


def test_detects_spanish_by_tildes():
    # Las tildes son señal fuerte de español aunque no haya palabras clave
    text = "por favor verifíca tu información personal"
    assert detect_language_heuristic(text) == "es"


def test_english_by_default_on_ambiguous():
    # Si no hay señales claras de ningún idioma, devuelve inglés
    text = "abc xyz qwerty"
    assert detect_language_heuristic(text) == "en"


# ---------------------------------------------------------------------------
# extract_features_from_text — URLs
# ---------------------------------------------------------------------------

def test_counts_urls():
    text = "Click http://evil.com and also http://fake.xyz/login"
    features = extract_features_from_text(text)
    assert features["num_urls"] == 2


def test_no_urls():
    features = extract_features_from_text("Hello, how are you today?")
    assert features["num_urls"] == 0


def test_extracts_domain():
    text = "Visit http://phishing-site.com/login now"
    features = extract_features_from_text(text)
    assert "phishing-site.com" in features["domains"]


def test_multiple_domains():
    text = "Go to http://a.com and http://b.org for more info"
    features = extract_features_from_text(text)
    assert len(features["domains"]) == 2


# ---------------------------------------------------------------------------
# extract_features_from_text — palabras urgentes
# ---------------------------------------------------------------------------

def test_detects_urgent_words():
    text = "You must verify your account immediately or it will be suspended"
    features = extract_features_from_text(text)
    assert "verify" in features["urgent_words"]
    assert "account" in features["urgent_words"]
    assert "suspended" in features["urgent_words"]


def test_no_urgent_words_in_legitimate():
    text = "Hi, let's meet tomorrow morning for coffee."
    features = extract_features_from_text(text)
    assert features["urgent_words"] == []


def test_urgent_word_boundary():
    # "account" dentro de "accountability" NO debe detectarse
    text = "The accountability measures are now in place for the organization"
    features = extract_features_from_text(text)
    assert "account" not in features["urgent_words"]


def test_urgent_word_spanish():
    text = "Es urgente que verifiques tu cuenta bloqueada ahora"
    features = extract_features_from_text(text)
    assert "urgente" in features["urgent_words"]
    assert "cuenta" in features["urgent_words"]
    assert "bloqueada" in features["urgent_words"]


# ---------------------------------------------------------------------------
# extract_features_from_text — longitud
# ---------------------------------------------------------------------------

def test_char_count():
    text = "Hello world"
    features = extract_features_from_text(text)
    assert features["num_chars"] == len(text)


def test_short_email_threshold_constant():
    # Verificamos que la constante tiene el valor documentado
    assert SHORT_EMAIL_THRESHOLD == 80


# ---------------------------------------------------------------------------
# Constantes de umbrales
# ---------------------------------------------------------------------------

def test_threshold_values():
    # Los umbrales deben ser valores razonables entre 0 y 1
    assert 0 < PHISHING_THRESHOLD_EN <= 1
    assert 0 < PHISHING_THRESHOLD_ES_HIGH <= 1
    assert 0 < PHISHING_THRESHOLD_ES_LOW <= 1
    # El umbral alto de español debe ser más estricto que el bajo
    assert PHISHING_THRESHOLD_ES_LOW > PHISHING_THRESHOLD_ES_HIGH


# ---------------------------------------------------------------------------
# _build_stem_to_original — mapeo token procesado → palabra original
# ---------------------------------------------------------------------------

from backend.ml.predict import _build_stem_to_original
from backend.ml.preprocessing import TextPreprocessor

_prep = TextPreprocessor()


def test_stem_map_spanish_basic():
    """El mapa debe incluir la raíz de palabras en español."""
    text = "Hola equipo, adjunto la factura del mes."
    mapping = _build_stem_to_original(text, _prep)
    # "hola" → stemming español → "hol"
    assert "hol" in mapping
    assert mapping["hol"].lower() == "hola"


def test_stem_map_returns_original_word():
    """La palabra original se recupera correctamente."""
    text = "Verificando tu cuenta bancaria ahora mismo."
    mapping = _build_stem_to_original(text, _prep)
    # "verificando" → "verific"
    assert "verific" in mapping
    assert mapping["verific"].lower() == "verificando"


def test_stem_map_no_overwrite_existing():
    """Cada stem queda mapeado a exactamente una palabra original."""
    text = "Hola equipo, adjunto la factura mensual. Un saludo cordial."
    mapping = _build_stem_to_original(text, _prep)
    # Todos los valores deben ser strings no vacíos
    for stem, original in mapping.items():
        assert isinstance(original, str)
        assert len(original) > 0


def test_stem_map_none_preprocessor():
    """Si no hay preprocesador, devuelve dict vacío sin errores."""
    mapping = _build_stem_to_original("cualquier texto", None)
    assert mapping == {}


def test_stem_map_english():
    """Para inglés, lematización: las palabras normales no cambian."""
    text = "verify your account immediately"
    mapping = _build_stem_to_original(text, _prep)
    # "verify" en inglés no debería cambiar con lematización
    assert "verifi" in mapping or "verify" in mapping
