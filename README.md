# inbox-triage

Classify and archive emails in your Fastmail inbox using a local LLM (Ollama) that reads each email and categorizes it as actionable, informational, or noise.

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` with your credentials:
- **FASTMAIL_USER**: your Fastmail email address
- **FASTMAIL_TOKEN**: generate at Fastmail → Settings → Privacy & Security → API Tokens (needs Mail read/write access)
- **OLLAMA_URL** (optional): Ollama server URL (default: `http://100.114.52.102:11434`)
- **OLLAMA_MODEL** (optional): model to use (default: `llama3.1:latest`)

Requires [Ollama](https://ollama.ai) running with a model pulled (e.g. `ollama pull llama3.1`).

## Usage

### Classify and archive

```bash
# Dry run (default) — shows what would be archived
uv run inbox-triage run

# Actually archive
uv run inbox-triage run --execute

# Limit number of emails to process
uv run inbox-triage run --limit 50
```

The LLM classifies each email into one of three categories:

| Category | Meaning | Action |
|----------|---------|--------|
| `action_needed` | Requires reply, decision, or task | Stays in inbox |
| `fyi` | Worth reading, no action needed | Stays in inbox |
| `noise` | Receipts, notifications, marketing, newsletters | Auto-archived |

Duplicate emails (same sender + subject + content) are also archived.

### Review inbox

```bash
uv run inbox-triage review
```

Shows `action_needed` and `fyi` emails with the LLM's reasoning. You can flag emails for follow-up from this view.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
