import os

import joblib

from inbox_triage.features import extract_features_batch
from inbox_triage.train import MODEL_PATH


def _load_model():
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Model not found at {MODEL_PATH}. Run 'inbox-triage train' first."
        )
    return joblib.load(MODEL_PATH)


def classify_emails(emails: list[dict], threshold: float = 0.85) -> list[dict]:
    model = _load_model()
    features = extract_features_batch(emails)
    probas = model.predict_proba(features)[:, 1]  # class 1 = transactional

    results = [
        {"email": email, "probability": float(prob)}
        for email, prob in zip(emails, probas)
        if prob >= threshold
    ]
    results.sort(key=lambda x: x["probability"], reverse=True)
    return results


def get_uncertain_emails(
    emails: list[dict], low: float = 0.5, high: float = 0.85
) -> list[dict]:
    model = _load_model()
    features = extract_features_batch(emails)
    probas = model.predict_proba(features)[:, 1]

    results = [
        {"email": email, "probability": float(prob)}
        for email, prob in zip(emails, probas)
        if low <= prob < high
    ]
    results.sort(key=lambda x: x["probability"], reverse=True)
    return results
