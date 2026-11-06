"""
preprocessing.py
================
Pipeline de preprocesado NLP explícito para correos electrónicos.

Pasos aplicados en orden a cada correo:
  1. Minúsculas
  2. Sustitución de URLs por el token especial «url»
  3. Eliminación de caracteres no alfabéticos (puntuación, números, etc.)
  4. Tokenización (split por espacios tras la limpieza)
  5. Detección automática de idioma (EN / ES)
  6. Eliminación de stopwords en el idioma detectado
  7. Lematización (inglés) o Stemming (español)
  8. Reconstrucción del texto limpio

La clase TextPreprocessor hereda de BaseEstimator y TransformerMixin
de scikit-learn, por lo que puede encadenarse directamente dentro de
un Pipeline de sklearn:

    Pipeline([
        ('preprocessor', TextPreprocessor()),
        ('tfidf', TfidfVectorizer(...)),
        ('clf',  LogisticRegression(...)),
    ])

Uso independiente:
    from backend.ml.preprocessing import TextPreprocessor
    prep = TextPreprocessor()
    textos_limpios = prep.transform(["Verify your account now!"])
"""

from __future__ import annotations

import re
from typing import List

import nltk
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer, WordNetLemmatizer
from sklearn.base import BaseEstimator, TransformerMixin


# ---------------------------------------------------------------------------
# Descarga automática de recursos NLTK necesarios
# ---------------------------------------------------------------------------

def ensure_nltk_data() -> None:
    """
    Comprueba si los recursos NLTK están descargados y los descarga
    automáticamente si no están presentes. Solo descarga una vez.
    Nota: no necesitamos 'punkt' porque usamos split() propio tras la limpieza regex.
    """
    recursos = [
        ("corpora/stopwords", "stopwords"),
        ("corpora/wordnet",   "wordnet"),
        ("corpora/omw-1.4",   "omw-1.4"),
    ]
    for ruta, nombre in recursos:
        try:
            nltk.data.find(ruta)
        except (LookupError, OSError):
            print(f"[NLTK] Descargando recurso '{nombre}' ...")
            nltk.download(nombre, quiet=True)


ensure_nltk_data()


# ---------------------------------------------------------------------------
# Palabras clave para detección de idioma
# ---------------------------------------------------------------------------

_SPANISH_HINTS = {
    "hola", "buenas", "estimado", "estimada", "usted", "gracias",
    "adjunto", "factura", "curso", "universidad", "saludo", "para",
    "correo", "cuenta", "banco", "envío", "por", "favor", "desde",
}

_ENGLISH_HINTS = {
    "hello", "dear", "please", "regards", "invoice", "university",
    "course", "thank", "from", "your", "account", "verify", "click",
    "here", "best", "sincerely", "attached",
}

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

_URL_RE    = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_ALPHA_RE  = re.compile(r"[^a-záéíóúüñàèìòùa-z\s]")
_SPACE_RE  = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class TextPreprocessor(BaseEstimator, TransformerMixin):
    """
    Preprocesador de texto bilingüe (EN/ES) compatible con scikit-learn.

    Parámetros
    ----------
    n_jobs : int
        Número de procesos paralelos para transformar textos.
        -1 = usar todos los núcleos disponibles.
    min_token_len : int
        Longitud mínima de un token para ser conservado (filtra ruido).
    """

    def __init__(self, min_token_len: int = 3) -> None:
        self.min_token_len = min_token_len

        # Herramientas NLTK
        self._lemmatizer = WordNetLemmatizer()          # Inglés → forma base
        self._stemmer_es  = SnowballStemmer("spanish")  # Español → raíz
        self._stops_en    = set(stopwords.words("english"))
        self._stops_es    = set(stopwords.words("spanish"))

    # ------------------------------------------------------------------
    # Interfaz sklearn (fit no aprende nada: el preprocesado es fijo)
    # ------------------------------------------------------------------

    def fit(self, X, y=None):
        return self

    def transform(self, X) -> List[str]:
        """
        Aplica el pipeline NLP a una lista de textos.
        Devuelve una lista de strings limpios.
        Nota: se procesa de forma secuencial porque WordNetLemmatizer
        de NLTK no es thread-safe.
        """
        return [self._preprocess(text) for text in X]

    # ------------------------------------------------------------------
    # Pipeline interno
    # ------------------------------------------------------------------

    def _preprocess(self, text: str) -> str:
        """Aplica todos los pasos a un único correo."""

        # Paso 1 — Minúsculas
        text = text.lower()

        # Paso 2 — Sustituir URLs por token especial
        # Mantener la información de que había un enlace sin guardar la URL
        text = _URL_RE.sub(" url ", text)

        # Paso 3 — Eliminar caracteres no alfabéticos
        # Se conservan letras (incluyendo acentos y ñ) y espacios
        text = _ALPHA_RE.sub(" ", text)

        # Paso 4 — Normalizar espacios múltiples
        text = _SPACE_RE.sub(" ", text).strip()

        # Paso 5 — Tokenización (split simple tras la limpieza)
        tokens = text.split()

        # Paso 6 — Detección de idioma basada en solapamiento con stopwords
        lang = self._detect_language(tokens)

        # Paso 7 — Eliminación de stopwords + lematización / stemming
        if lang == "es":
            tokens = self._process_es(tokens)
        else:
            tokens = self._process_en(tokens)

        # Paso 8 — Filtrar tokens muy cortos (ruido)
        tokens = [t for t in tokens if len(t) >= self.min_token_len]

        return " ".join(tokens)

    # ------------------------------------------------------------------
    # Detección de idioma
    # ------------------------------------------------------------------

    def _detect_language(self, tokens: List[str]) -> str:
        """
        Heurística rápida: cuenta cuántas palabras del texto aparecen
        en los conjuntos de pistas de cada idioma.
        También usa las tildes como señal fuerte de español.
        """
        token_set = set(tokens)

        es_score = len(token_set & _SPANISH_HINTS)
        en_score = len(token_set & _ENGLISH_HINTS)

        # Las tildes son una señal fiable de español
        if any(c in "áéíóúüñ" for t in tokens for c in t):
            es_score += 2

        return "es" if es_score >= en_score else "en"

    # ------------------------------------------------------------------
    # Procesado por idioma
    # ------------------------------------------------------------------

    def _process_en(self, tokens: List[str]) -> List[str]:
        """
        Inglés:
          - Elimina stopwords en inglés ('the', 'is', 'at', 'which'...)
          - Lematización: reduce cada palabra a su forma base en el
            diccionario. Ejemplo: 'running' → 'run', 'accounts' → 'account'.
        """
        resultado = []
        for token in tokens:
            if token in self._stops_en:
                continue
            lema = self._lemmatizer.lemmatize(token)
            resultado.append(lema)
        return resultado

    def _process_es(self, tokens: List[str]) -> List[str]:
        """
        Español:
          - Elimina stopwords en español ('de', 'la', 'que', 'el'...)
          - Stemming con SnowballStemmer: reduce cada palabra a su raíz
            morfológica. Ejemplo: 'verificando' → 'verific', 'cuenta' → 'cuent'.

        Nota: Para español usamos stemming (raíz) en lugar de lematización
        (forma del diccionario) porque NLTK no incluye un lematizador
        completo para español. El stemming es una aproximación válida
        y muy usada en NLP en español.
        """
        resultado = []
        for token in tokens:
            if token in self._stops_es:
                continue
            raiz = self._stemmer_es.stem(token)
            resultado.append(raiz)
        return resultado


# ---------------------------------------------------------------------------
# Demo rápida si se ejecuta directamente
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ejemplos = [
        "Your account has been suspended. Verify your password immediately at http://fake-bank.xyz/login",
        "Estimado usuario, su cuenta bancaria ha sido bloqueada. Verifique sus datos en http://phishing.es/login",
        "Hi team, the meeting is scheduled for tomorrow at 10am. Please confirm your attendance.",
        "Hola equipo, te adjunto la factura del mes de marzo. Un saludo.",
    ]

    prep = TextPreprocessor()
    print("=== Demo TextPreprocessor ===\n")
    for original in ejemplos:
        limpio = prep.transform([original])[0]
        print(f"ORIGINAL : {original[:80]}...")
        print(f"LIMPIO   : {limpio}")
        print()
