import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.pipeline import Pipeline

from inbox_triage.dedup import deduplicate_emails
from inbox_triage.features import extract_features_batch
from inbox_triage.jmap import JMAPClient

MODEL_PATH = "model.joblib"


def train_model(client: JMAPClient, limit: int = 10000) -> tuple[Pipeline, dict]:
    emails = client.get_archive_emails(limit=limit)
    if not emails:
        raise RuntimeError("No emails found in archive")

    # Add flagged inbox emails as additional "keep" training data
    flagged_inbox = client.get_flagged_inbox_emails()
    if flagged_inbox:
        seen_ids = {e["id"] for e in emails}
        for e in flagged_inbox:
            if e["id"] not in seen_ids:
                emails.append(e)

    # Dedup training data (prefers flagged copy, then newest)
    emails, _dupes = deduplicate_emails(emails)

    features = extract_features_batch(emails)

    # Label: 0 = keep (flagged), 1 = transactional (unflagged)
    labels = np.array([
        0 if "$flagged" in (e.get("keywords") or {}) else 1 for e in emails
    ])

    n_keep = int((labels == 0).sum())
    n_trans = int((labels == 1).sum())
    total = len(labels)
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    # Cross-validation with predict_proba to evaluate at runtime threshold (0.90)
    n_splits = min(5, n_keep, n_trans)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    probas = cross_val_predict(pipeline, features, labels, cv=cv, method="predict_proba")
    transactional_proba = probas[:, 1]  # class 1 = transactional
    predictions = (transactional_proba >= 0.90).astype(int)

    false_archives = []
    false_keeps = []
    for i in range(len(labels)):
        if predictions[i] != labels[i]:
            email = emails[i]
            entry = {
                "email": email,
                "actual": "keep" if labels[i] == 0 else "transactional",
                "predicted": "keep" if predictions[i] == 0 else "transactional",
            }
            if labels[i] == 0 and predictions[i] == 1:
                false_archives.append(entry)
            else:
                false_keeps.append(entry)

    metrics = {
        "n_emails": total,
        "n_keep": n_keep,
        "n_transactional": n_trans,
        "false_archives": false_archives,
        "false_keeps": false_keeps,
    }

    # Fit on full dataset
    pipeline.fit(features, labels)

    joblib.dump(pipeline, MODEL_PATH)

    return pipeline, metrics
