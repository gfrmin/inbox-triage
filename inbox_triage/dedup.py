import re

_RE_PREFIX = re.compile(r"^(re|fwd?|fw)\s*:\s*", re.IGNORECASE)


def deduplicate_emails(emails: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group emails by sender+subject+content, keep best per group, return (keep, dupes).

    Prefers flagged copies, then newest.
    """

    def _normalize_preview(email):
        preview = re.sub(r"\s+", " ", (email.get("preview") or "")).strip().lower()
        return preview[:80]

    def _key(email):
        from_list = email.get("from") or []
        sender = from_list[0].get("email", "").lower() if from_list else ""
        subject = _RE_PREFIX.sub("", email.get("subject") or "").strip().lower()
        return (sender, subject, _normalize_preview(email))

    groups: dict[tuple, list[dict]] = {}
    for email in emails:
        groups.setdefault(_key(email), []).append(email)

    keep, dupes = [], []
    for group in groups.values():
        if len(group) == 1:
            keep.append(group[0])
        else:
            # Prefer flagged, then newest
            group.sort(key=lambda e: (
                "$flagged" in (e.get("keywords") or {}),
                e.get("receivedAt", ""),
            ), reverse=True)
            keep.append(group[0])
            dupes.extend(group[1:])

    return keep, dupes
