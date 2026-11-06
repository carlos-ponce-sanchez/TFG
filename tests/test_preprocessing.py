"""
tests/test_preprocessing.py
============================
Tests unitarios para el módulo de preprocesado NLP (TextPreprocessor).

Qué se comprueba:
  - Que el texto se convierte a minúsculas
  - Que las URLs se sustituyen por el token 'url'
  - Que los caracteres no alfabéticos se eliminan
  - Que los tokens cortos (< 3 caracteres) se filtran
  - Que el preprocesador devuelve el tipo correcto
  - Que las stopwords en inglés se eliminan
  - Que las stopwords en español se eliminan
  - Que un texto vacío no provoca errores
"""

import pytest
from backend.ml.preprocessing import TextPreprocessor


@pytest.fixture(scope="module")
def prep():
    """Instancia de TextPreprocessor reutilizada en todos los tests del módulo."""
    return TextPreprocessor()


# ---------------------------------------------------------------------------
# Paso 1: Minúsculas
# ---------------------------------------------------------------------------

def test_lowercase(prep):
    result = prep.transform(["HELLO WORLD URGENT"])[0]
    assert result == result.lower()


# ---------------------------------------------------------------------------
# Paso 2: URLs sustituidas por token 'url'
# ---------------------------------------------------------------------------

def test_url_replaced_by_token(prep):
    result = prep.transform(["Visit http://fake-bank.xyz/login now"])[0]
    assert "url" in result
    assert "http" not in result
    assert "fake-bank" not in result


def test_www_url_replaced(prep):
    result = prep.transform(["Go to www.evil-site.com immediately"])[0]
    assert "url" in result
    assert "www" not in result


# ---------------------------------------------------------------------------
# Paso 3: Eliminación de caracteres no alfabéticos
# ---------------------------------------------------------------------------

def test_removes_punctuation(prep):
    result = prep.transform(["hello!!! verify#now @bank"])[0]
    assert "!" not in result
    assert "#" not in result
    assert "@" not in result


def test_removes_numbers(prep):
    result = prep.transform(["your pin is 4321 verify now"])[0]
    assert "4321" not in result


# ---------------------------------------------------------------------------
# Paso 8: Tokens cortos filtrados
# ---------------------------------------------------------------------------

def test_short_tokens_filtered(prep):
    result = prep.transform(["hi ok it is a good day for us"])[0]
    tokens = result.split()
    assert all(len(t) >= 3 for t in tokens), \
        f"Se encontraron tokens de menos de 3 caracteres: {tokens}"


# ---------------------------------------------------------------------------
# Tipo de retorno
# ---------------------------------------------------------------------------

def test_transform_returns_list(prep):
    result = prep.transform(["hello world", "hola mundo"])
    assert isinstance(result, list)
    assert len(result) == 2


def test_each_element_is_string(prep):
    result = prep.transform(["verify your account now"])
    assert isinstance(result[0], str)


# ---------------------------------------------------------------------------
# Paso 7: Stopwords inglés eliminadas
# ---------------------------------------------------------------------------

def test_english_stopwords_removed(prep):
    # "your", "has", "been" son stopwords en inglés
    result = prep.transform(["your account has been suspended"])[0]
    tokens = result.split()
    assert "has" not in tokens
    assert "been" not in tokens


# ---------------------------------------------------------------------------
# Paso 7: Stopwords español eliminadas
# ---------------------------------------------------------------------------

def test_spanish_stopwords_removed(prep):
    # "ha", "sido", "su" son stopwords en español
    result = prep.transform(["hola estimado usuario su cuenta ha sido bloqueada"])[0]
    tokens = result.split()
    assert "ha" not in tokens
    assert "sido" not in tokens


# ---------------------------------------------------------------------------
# Casos borde
# ---------------------------------------------------------------------------

def test_empty_string_no_error(prep):
    result = prep.transform([""])[0]
    assert isinstance(result, str)


def test_batch_transform(prep):
    texts = [
        "Your account has been suspended",
        "Estimado usuario, verifique su cuenta",
        "Hi team, meeting tomorrow at 10am",
    ]
    results = prep.transform(texts)
    assert len(results) == len(texts)
    assert all(isinstance(r, str) for r in results)
