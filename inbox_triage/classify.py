import json
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://100.114.52.102:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:latest")

SYSTEM_PROMPT = """\
You are an email triage assistant. Classify each email into exactly one category.

Categories:
- action_needed: requires a reply, decision, or task from the recipient
- fyi: worth reading but no action needed (updates from known contacts, relevant news)
- noise: transactional receipts, automated notifications, marketing, newsletters, shipping updates

Respond with JSON: {"category": "...", "reason": "brief explanation"}\
"""


def _build_user_message(email: dict) -> str:
    from_list = email.get("from") or []
    sender = from_list[0].get("email", "unknown") if from_list else "unknown"
    subject = email.get("subject") or "(no subject)"
    preview = (email.get("preview") or "")[:300]

    parts = [f"From: {sender}", f"Subject: {subject}"]
    if preview:
        parts.append(f"Preview: {preview}")
    return "\n".join(parts)


def classify_email(email: dict) -> dict:
    """Classify a single email via Ollama. Returns {category, reason}."""
    resp = httpx.post(
        f"{OLLAMA_URL}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(email)},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    category = parsed.get("category", "fyi")
    if category not in ("action_needed", "fyi", "noise"):
        category = "fyi"

    return {"category": category, "reason": parsed.get("reason", "")}


def classify_emails(emails: list[dict]) -> list[dict]:
    """Classify a batch of emails sequentially. Returns [{email, category, reason}]."""
    results = []
    for email in emails:
        result = classify_email(email)
        results.append({
            "email": email,
            "category": result["category"],
            "reason": result["reason"],
        })
    return results
