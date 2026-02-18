import re

_NOREPLY_PATTERN = re.compile(
    r"^(noreply|no-reply|notifications?|receipts?|mailer|newsletter|info|support|alerts?|updates?)@",
    re.IGNORECASE,
)


def extract_features(email: dict) -> str:
    parts = []

    # Sender address and domain
    from_list = email.get("from") or []
    if from_list:
        addr = from_list[0].get("email", "")
        parts.append(addr)
        if "@" in addr:
            parts.append(addr.split("@")[1])

        # Noreply sender check
        if _NOREPLY_PATTERN.match(addr):
            parts.append("NOREPLY_SENDER")

    # Subject
    subject = email.get("subject") or ""
    parts.append(subject)

    # List-Unsubscribe header
    if email.get("header:List-Unsubscribe") is not None:
        parts.append("HAS_LIST_UNSUBSCRIBE")

    # Precedence header
    precedence = email.get("header:Precedence")
    if precedence and any(w in precedence.lower() for w in ("bulk", "list")):
        parts.append("PRECEDENCE_BULK")

    # X-Mailer header
    if email.get("header:X-Mailer") is not None:
        parts.append("HAS_XMAILER")

    # Preview (first 200 chars)
    preview = email.get("preview") or ""
    parts.append(preview[:200])

    return " ".join(parts)


def extract_features_batch(emails: list[dict]) -> list[str]:
    return [extract_features(e) for e in emails]
