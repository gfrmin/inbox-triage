# inbox-triage

Email triage CLI that classifies Fastmail inbox emails via local Ollama LLM and archives noise.

## Architecture

- `inbox_triage/jmap.py` — JMAP client for Fastmail (fetch emails, move, flag)
- `inbox_triage/classify.py` — LLM classifier using Ollama's OpenAI-compatible API (`/v1/chat/completions`)
- `inbox_triage/dedup.py` — Deduplicates emails by sender+subject+preview
- `inbox_triage/cli.py` — Click CLI with `run` (classify+archive) and `review` (inspect+flag) commands

## Key details

- Ollama URL defaults to `http://100.114.52.102:11434` (Tailscale), configurable via `OLLAMA_URL` env var
- Uses OpenAI-compatible endpoint, not legacy `/api/chat`
- Model defaults to `llama3.1:latest`, configurable via `OLLAMA_MODEL`
- Classification categories: `action_needed`, `fyi`, `noise` — only `noise` gets archived
- Emails processed sequentially (~0.7s each)
- Fastmail credentials via `FASTMAIL_USER` and `FASTMAIL_TOKEN` env vars (loaded from `.env`)
- Dependencies: httpx, click, rich, python-dotenv (no ML libraries)
- Classification cache at `$XDG_CACHE_HOME/inbox-triage/classifications.json` (key: `{model}:{email_id}`); bypass with `--no-cache`
