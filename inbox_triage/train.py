import sys

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline

from inbox_triage.features import extract_features_batch
from inbox_triage.jmap import JMAPClient

MODEL_PATH = "model.joblib"


def train_model(client: JMAPClient) -> tuple[Pipeline, dict]:
    emails = client.get_inbox_emails(limit=500)
    if not emails:
        raise RuntimeError("No emails found in inbox")

    features = extract_features_batch(emails)

    # Label: 0 = keep (flagged), 1 = transactional (unflagged)
    labels = np.array([
        0 if "$flagged" in (e.get("keywords") or {}) else 1 for e in emails
    ])

    # Check class balance
    n_keep = int((labels == 0).sum())
    n_trans = int((labels == 1).sum())
    total = len(labels)
    if n_keep / total < 0.2 or n_trans / total < 0.2:
        print(
            f"WARNING: Imbalanced classes — {n_keep} keep ({n_keep/total:.0%}), "
            f"{n_trans} transactional ({n_trans/total:.0%}). "
            "Flag more emails to improve accuracy.",
            file=sys.stderr,
        )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])

    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accuracy_scores = cross_val_score(pipeline, features, labels, cv=cv, scoring="accuracy")
    f1_scores = cross_val_score(pipeline, features, labels, cv=cv, scoring="f1")

    metrics = {
        "accuracy_mean": float(accuracy_scores.mean()),
        "accuracy_std": float(accuracy_scores.std()),
        "f1_mean": float(f1_scores.mean()),
        "f1_std": float(f1_scores.std()),
        "n_emails": total,
        "n_keep": n_keep,
        "n_transactional": n_trans,
    }

    # Fit on full dataset
    pipeline.fit(features, labels)

    joblib.dump(pipeline, MODEL_PATH)

    return pipeline, metrics
