# inbox-triage

Classify and archive transactional emails in your Fastmail inbox using a logistic regression classifier trained on your archived email patterns.

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` with your Fastmail credentials:
- **FASTMAIL_USER**: your Fastmail email address
- **FASTMAIL_TOKEN**: generate at Fastmail → Settings → Privacy & Security → API Tokens (needs Mail read/write access)

## Usage

### Train the model

Training uses your **Archive** folder as labeled data, plus any flagged emails still in your inbox. Flag emails you consider important, then archive them. The classifier learns from this:

- **Flagged** = "keep" (important)
- **Unflagged + archived** = "transactional" (swept away)

```bash
uv run inbox-triage train
```

Training reports errors asymmetrically — false archives (important email archived) are dangerous, false keeps (junk left in inbox) are harmless:

```
  False archives (keep → trans):   16   ← dangerous
  False keeps (trans → keep):     2310   ← harmless
```

### Classify and archive

```bash
# Dry run (default) — shows what would be archived
uv run inbox-triage run

# Actually archive
uv run inbox-triage run --execute

# Adjust confidence threshold (default: 0.85)
uv run inbox-triage run --threshold 0.9
```

### Review uncertain emails

```bash
uv run inbox-triage review
```

Shows emails in the 0.5–0.85 confidence band. Flag important ones and re-train to improve accuracy.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
