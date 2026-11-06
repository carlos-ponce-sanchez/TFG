from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import joblib

# ── Constantes de decisión ────────────────────────────────────────────────────
# Umbral mínimo de caracteres para considerar que un correo puede ser phishing.
# Correos más cortos que esto, sin URLs ni palabras urgentes, se clasifican
# como legítimos por defecto (son demasiado cortos para ser un ataque real).
SHORT_EMAIL_THRESHOLD = 80


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH   = BASE_DIR / "phishing_model.joblib"
BLACKLIST_PATH = BASE_DIR.parent.parent / "data" / "url_blacklist.txt"


def _load_blacklist() -> set:
    """Carga la lista negra de dominios desde disco. Ignora comentarios y líneas vacías."""
    if not BLACKLIST_PATH.exists():
        return set()
    with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
        return {
            line.strip().lower()
            for line in f
            if line.strip() and not line.startswith("#")
        }


BLACKLISTED_DOMAINS: set = _load_blacklist()


URGENT_WORDS = [
    "urgent",
    "immediately",
    "verify",
    "account",
    "password",
    "suspend",
    "suspended",
    "security",
    "confirm",
    "winner",
    "ganador",
    "urgente",
    "inmediatamente",
    "verifica",
    "cuenta",
    "contraseña",
    "bloqueada",
    "bloqueado",
]

# Umbrales base por encima de los cuales consideramos que la probabilidad de phishing es alta.
# Usamos valores distintos para inglés y español porque el modelo tiene menos datos
# de entrenamiento en español y sus predicciones son menos fiables en ese idioma.
PHISHING_THRESHOLD_EN = 0.8       # Inglés: alta confianza → umbral estricto
PHISHING_THRESHOLD_ES_HIGH = 0.5  # Español con URLs o palabras financieras → más sensible
PHISHING_THRESHOLD_ES_LOW  = 0.8  # Español sin contexto sospechoso → mismo umbral que inglés

# Alias mantenido por compatibilidad (valor original de PHISHING_THRESHOLD_ES)
PHISHING_THRESHOLD_ES = PHISHING_THRESHOLD_ES_HIGH


SPANISH_HINTS = [
    " hola ",
    " buenas ",
    " estimado",
    " estimada",
    " usted ",
    " tu ",
    " envío ",
    " adjunto",
    " factura",
    " curso",
    " universidad",
    " cuenta ",
    " gracias ",
    " saludo",
]

ENGLISH_HINTS = [
    " hello ",
    " dear ",
    " please ",
    " account",
    " verify",
    " regards",
    " invoice",
    " university",
    " course",
    " thank you",
    " best ",
]


URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)
DOMAIN_REGEX = re.compile(r"https?://([^/\s]+)", re.IGNORECASE)


def load_model():
    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"No se ha encontrado el modelo entrenado en {MODEL_PATH}. "
            "Ejecuta primero el script de entrenamiento (backend/ml/train.py)."
        )
    return joblib.load(MODEL_PATH)


def detect_language_heuristic(text: str) -> str:
    """
    Detección muy sencilla de idioma basada en la presencia de ciertas palabras
    frecuentes. No es perfecta, pero es suficiente para ajustar umbrales.
    """
    lowered = f" {text.lower()} "
    es_score = sum(lowered.count(token) for token in SPANISH_HINTS)
    en_score = sum(lowered.count(token) for token in ENGLISH_HINTS)

    if es_score > en_score:
        return "es"
    if en_score > es_score:
        return "en"
    # Empate o ninguno detectado: usamos una heurística por longitud y tildes.
    if any(c in lowered for c in "áéíóúñ"):
        return "es"
    return "en"


def extract_features_from_text(text: str) -> Dict[str, Any]:
    urls = URL_REGEX.findall(text)
    domains = DOMAIN_REGEX.findall(text)

    text_lower = text.lower()
    # Usamos \b (word boundary) para evitar falsos positivos: "account" no debe
    # encontrarse dentro de "accountability" o "accountant".
    urgent_found = [
        w for w in URGENT_WORDS
        if re.search(r"\b" + re.escape(w) + r"\b", text_lower)
    ]

    # Comprueba qué dominios detectados están en la lista negra
    blacklisted = [d for d in domains if d.lower() in BLACKLISTED_DOMAINS]

    return {
        "num_chars": len(text),
        "num_urls": len(urls),
        "urls": urls,
        "domains": domains,
        "blacklisted_domains": blacklisted,
        "urgent_words": urgent_found,
    }


def _extract_coef(classifier):
    """
    Intenta extraer los coeficientes del clasificador sea cual sea su tipo.
    Devuelve el array de coeficientes o None si el modelo no es lineal.

    Modelos soportados:
      - LogisticRegression           → classifier.coef_[0]
      - CalibratedClassifierCV(SVM)  → accede al estimador interno calibrado
      - Cualquier modelo con coef_   → classifier.coef_[0]
    """
    # Modelo lineal directo (LogisticRegression, SGDClassifier, etc.)
    if hasattr(classifier, "coef_"):
        return classifier.coef_[0]

    # CalibratedClassifierCV envuelve LinearSVC u otros modelos lineales.
    # En scikit-learn >= 1.0 los estimadores calibrados están en
    # calibrated_classifiers_, cada uno con un atributo .estimator.
    if hasattr(classifier, "calibrated_classifiers_"):
        try:
            base = classifier.calibrated_classifiers_[0].estimator
            if hasattr(base, "coef_"):
                return base.coef_[0]
        except Exception:
            pass

    # Fallback para versiones antiguas de sklearn
    for attr in ("base_estimator", "estimator"):
        sub = getattr(classifier, attr, None)
        if sub is not None and hasattr(sub, "coef_"):
            return sub.coef_[0]

    return None


def _build_stem_to_original(text: str, preprocessor) -> Dict[str, str]:
    """
    Construye un mapeo token_procesado → palabra_original del correo.

    Recorre las palabras del texto original, aplica el mismo preprocesado
    que el pipeline (minúsculas, limpieza, stemming/lematización) a cada una
    por separado y asocia el resultado con la palabra original.
    Cuando varias palabras originales producen el mismo token procesado,
    se conserva la primera aparición (es la más representativa).
    """
    if preprocessor is None:
        return {}

    mapping: Dict[str, str] = {}
    # Extraer palabras del texto original (solo letras y acentos)
    original_words = re.findall(r"[a-záéíóúüña-zA-ZÁÉÍÓÚÜÑ]+", text)

    for word in original_words:
        # Procesar cada palabra individualmente con el mismo pipeline
        processed = preprocessor.transform([word])[0].strip()
        if processed and processed not in mapping:
            mapping[processed] = word

    return mapping


def explain_with_linear_model(pipeline, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Devuelve los tokens que más han influido en la decisión del modelo.

    Cada token incluye la palabra original del correo (antes del stemming)
    para que el resultado sea comprensible por el usuario final.

    - Modelos lineales (LogReg, SVM): usa los coeficientes × TF-IDF.
      La contribución de cada palabra es exacta y matemáticamente interpretable.
    - Random Forest: usa las importancias de features × valor TF-IDF.
      Es una aproximación: indica qué palabras presentes en el correo
      coinciden con features globalmente importantes para el árbol.
    - MLP u otros: devuelve lista vacía (no hay forma directa de explicar).
    """
    try:
        vectorizer = pipeline.named_steps["tfidf"]
        classifier = pipeline.named_steps["clf"]
    except Exception:
        return []

    feature_names = vectorizer.get_feature_names_out()

    # Aplicar preprocesado si el pipeline lo incluye antes de transformar con TF-IDF
    preprocessor = pipeline.named_steps.get("preprocessor")
    text_for_tfidf = preprocessor.transform([text])[0] if preprocessor else text
    X = vectorizer.transform([text_for_tfidf])

    # Mapeo token_procesado → palabra original del correo
    stem_map = _build_stem_to_original(text, preprocessor)

    def _make_token_entry(token: str, contribution: float) -> Dict[str, Any]:
        """Construye la entrada de un token con su palabra original si existe."""
        entry: Dict[str, Any] = {"token": token, "contribution": contribution}
        original = stem_map.get(token)
        if original and original.lower() != token:
            entry["original"] = original
        return entry

    # ── Modelos lineales ──────────────────────────────────────────────────
    coefs = _extract_coef(classifier)

    if coefs is not None:
        contributions = X.multiply(coefs).toarray()[0]
        indexed = [
            (feature_names[i], contributions[i])
            for i in range(len(feature_names))
            if contributions[i] != 0
        ]
        indexed.sort(key=lambda x: abs(x[1]), reverse=True)
        return [_make_token_entry(t, float(s)) for t, s in indexed[:top_k]]

    # ── Random Forest: importancias de features ───────────────────────────
    if hasattr(classifier, "feature_importances_"):
        importances = classifier.feature_importances_
        X_arr = X.toarray()[0]
        contributions = X_arr * importances
        indexed = [
            (feature_names[i], float(contributions[i]))
            for i in range(len(feature_names))
            if contributions[i] != 0
        ]
        indexed.sort(key=lambda x: abs(x[1]), reverse=True)
        return [_make_token_entry(t, float(s)) for t, s in indexed[:top_k]]

    # ── MLP u otros modelos sin explicabilidad directa ────────────────────
    return []


def analyze_email_text(pipeline, text: str) -> Dict[str, Any]:
    proba = pipeline.predict_proba([text])[0]
    score_phishing = float(proba[1])
    basic_features = extract_features_from_text(text)
    token_importance = explain_with_linear_model(pipeline, text, top_k=10)

    detected_lang = detect_language_heuristic(text)
    basic_features["detected_lang"] = detected_lang
    text_lower = text.lower()

    # Regla heurística: mensajes muy cortos, sin enlaces y sin palabras de urgencia
    # son muy poco probables como phishing. Forzamos 'legítimo' en esos casos.
    if (
        basic_features["num_urls"] == 0
        and not basic_features["urgent_words"]
        and basic_features["num_chars"] < SHORT_EMAIL_THRESHOLD
    ):
        label = "legitimo"
        # Bajamos también la puntuación reportada para que encaje con la decisión.
        score_phishing = min(score_phishing, 0.2)
    else:
        # Decisión basada en el modelo con umbral según idioma detectado
        # y contexto (financiero o informativo).
        if detected_lang == "es":
            has_url = basic_features["num_urls"] > 0
            financial_keywords = [
                "banco",
                "tarjeta",
                "iban",
                "transferencia",
                "paypal",
                "pago",
                "cuenta bancaria",
                "banca online",
            ]
            suspicious_financial = any(k in text_lower for k in financial_keywords)

            # Si es español pero sin enlaces ni términos financieros claros,
            # exigimos un umbral alto para marcar phishing (priorizamos evitar falsos positivos).
            if not has_url and not suspicious_financial:
                threshold = PHISHING_THRESHOLD_ES_LOW
            else:
                threshold = PHISHING_THRESHOLD_ES_HIGH
        else:
            threshold = PHISHING_THRESHOLD_EN

        label = "phishing" if score_phishing >= threshold else "legitimo"

    return {
        "label": label,
        "score": score_phishing,
        "features": basic_features,
        "top_tokens": token_importance,
    }

