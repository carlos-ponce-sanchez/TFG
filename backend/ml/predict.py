from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import joblib


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "phishing_model.joblib"


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
# Usamos valores distintos para inglés y español porque el comportamiento del modelo
# no es idéntico en ambos idiomas.
PHISHING_THRESHOLD_EN = 0.8
PHISHING_THRESHOLD_ES = 0.5


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
    urgent_found = [w for w in URGENT_WORDS if w in text_lower]

    return {
        "num_chars": len(text),
        "num_urls": len(urls),
        "urls": urls,
        "domains": domains,
        "urgent_words": urgent_found,
    }


def explain_with_linear_model(pipeline, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    try:
        vectorizer = pipeline.named_steps["tfidf"]
        classifier = pipeline.named_steps["clf"]
    except Exception:
        return []

    X = vectorizer.transform([text])
    feature_names = vectorizer.get_feature_names_out()

    coefs = classifier.coef_[0]

    contributions = X.multiply(coefs).toarray()[0]

    indexed_contribs = [
        (feature_names[i], contributions[i]) for i in range(len(feature_names)) if contributions[i] != 0
    ]
    indexed_contribs.sort(key=lambda x: abs(x[1]), reverse=True)

    top_tokens = indexed_contribs[:top_k]

    return [
        {"token": token, "contribution": float(score)}
        for token, score in top_tokens
    ]


def analyze_email_text(pipeline, text: str) -> Dict[str, Any]:
    proba = pipeline.predict_proba([text])[0]
    score_phishing = float(proba[1])
    basic_features = extract_features_from_text(text)
    token_importance = explain_with_linear_model(pipeline, text)

    detected_lang = detect_language_heuristic(text)
    basic_features["detected_lang"] = detected_lang
    text_lower = text.lower()

    # Regla heurística: mensajes muy cortos, sin enlaces y sin palabras de urgencia
    # son muy poco probables como phishing. Forzamos 'legítimo' en esos casos.
    if (
        basic_features["num_urls"] == 0
        and not basic_features["urgent_words"]
        and basic_features["num_chars"] < 80
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
                threshold = 0.8
            else:
                threshold = PHISHING_THRESHOLD_ES
        else:
            threshold = PHISHING_THRESHOLD_EN

        label = "phishing" if score_phishing >= threshold else "legitimo"

    return {
        "label": label,
        "score": score_phishing,
        "features": basic_features,
        "top_tokens": token_importance,
    }

