import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from inbox_triage.classify import classify_emails
from inbox_triage.dedup import deduplicate_emails
from inbox_triage.jmap import JMAPClient

load_dotenv()

console = Console()


def _sender(email: dict) -> str:
    from_list = email.get("from") or []
    if from_list:
        return from_list[0].get("email", "unknown")
    return "unknown"


CATEGORY_STYLES = {
    "action_needed": "bold red",
    "fyi": "yellow",
    "noise": "dim",
}


@click.group()
def cli():
    """Inbox triage — classify and archive emails using LLM."""


@cli.command()
@click.option("--dry-run/--execute", default=True, help="Dry run (default) or execute archiving.")
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
def run(dry_run: bool, limit: int):
    """Classify inbox emails and archive noise."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)
    console.print(f"Fetched {len(emails)} emails. Classifying with LLM...")

    results = classify_emails(emails)

    noise = [r for r in results if r["category"] == "noise"]

    # Dedup among non-noise emails
    noise_ids = {r["email"]["id"] for r in noise}
    keep_emails = [e for e in emails if e["id"] not in noise_ids]
    _unique, dupes = deduplicate_emails(keep_emails)

    if not noise and not dupes:
        console.print("No emails to archive.")
        return

    if noise:
        table = Table(title="Noise (will be archived)")
        table.add_column("Sender", style="cyan", max_width=35)
        table.add_column("Subject", max_width=50)
        table.add_column("Reason", style="dim", max_width=40)

        for r in noise:
            table.add_row(
                _sender(r["email"]),
                (r["email"].get("subject") or "")[:50],
                r["reason"][:40],
            )

        console.print(table)

    if dupes:
        dupe_table = Table(title="Duplicate Emails (older copies)")
        dupe_table.add_column("Sender", style="cyan", max_width=35)
        dupe_table.add_column("Subject", max_width=50)
        dupe_table.add_column("Date", style="dim")

        for d in sorted(dupes, key=lambda e: e.get("receivedAt", ""), reverse=True):
            dupe_table.add_row(
                _sender(d),
                (d.get("subject") or "")[:50],
                (d.get("receivedAt") or "")[:10],
            )

        console.print(dupe_table)

    all_archive_ids = [r["email"]["id"] for r in noise] + [d["id"] for d in dupes]

    if dry_run:
        console.print(
            f"\n[yellow]{len(noise)} noise + {len(dupes)} duplicates = "
            f"{len(all_archive_ids)} emails would be archived.[/yellow]"
        )
    else:
        archive_id = client.get_mailbox_id("archive")
        client.batch_move(all_archive_ids, archive_id)
        console.print(
            f"\n[green]{len(noise)} noise + {len(dupes)} duplicates = "
            f"{len(all_archive_ids)} emails archived.[/green]"
        )


@cli.command()
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
def review(limit: int):
    """Show classified emails — action_needed and fyi — with reasons."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)
    console.print(f"Fetched {len(emails)} emails. Classifying with LLM...")

    results = classify_emails(emails)

    reviewable = [r for r in results if r["category"] != "noise"]

    if not reviewable:
        console.print("No action_needed or fyi emails found.")
        return

    table = Table(title="Inbox Review")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Category", max_width=15)
    table.add_column("Sender", style="cyan", max_width=35)
    table.add_column("Subject", max_width=50)
    table.add_column("Reason", style="dim", max_width=40)

    for i, r in enumerate(reviewable):
        style = CATEGORY_STYLES.get(r["category"], "")
        table.add_row(
            str(i),
            f"[{style}]{r['category']}[/{style}]",
            _sender(r["email"]),
            (r["email"].get("subject") or "")[:50],
            r["reason"][:40],
        )

    console.print(table)
    console.print(f"\n{len(reviewable)} emails to review.")

    selection = console.input(
        "\n[bold]Flag for follow-up[/bold] (comma-separated numbers, 'all', or Enter to skip): "
    ).strip()

    if not selection:
        return

    if selection.lower() == "all":
        indices = list(range(len(reviewable)))
    else:
        indices = []
        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                indices.extend(range(int(lo), int(hi) + 1))
            else:
                indices.append(int(part))
        indices = [i for i in indices if 0 <= i < len(reviewable)]

    if not indices:
        console.print("No valid indices.")
        return

    email_ids = [reviewable[i]["email"]["id"] for i in indices]
    client.batch_set_flag(email_ids, flagged=True)
    console.print(f"\n[green]Flagged {len(email_ids)} emails for follow-up.[/green]")
