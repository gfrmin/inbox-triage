# inbox-triage

Classify and archive transactional emails in your Fastmail inbox using a logistic regression classifier trained on your own flagged/unflagged email patterns.

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

Flag emails in your inbox that you want to **keep**, then:

```bash
uv run inbox-triage train
```

Flagged emails = "keep". Unflagged = "transactional" (archive candidates).

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
