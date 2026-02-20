import json
import os
from pathlib import Path


def _cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "inbox-triage" / "classifications.json"


def load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_cache(cache: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache))


def cache_key(model: str, email_id: str) -> str:
    return f"{model}:{email_id}"


def partition_by_cache(
    emails: list[dict], cache: dict, model: str
) -> tuple[list[dict], list[dict]]:
    """Split emails into (cached hits, uncached misses)."""
    hits, misses = [], []
    for email in emails:
        key = cache_key(model, email["id"])
        if key in cache:
            hits.append({"email": email, **cache[key]})
        else:
            misses.append(email)
    return hits, misses
