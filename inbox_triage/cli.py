import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from inbox_triage.classify import classify_emails, get_uncertain_emails
from inbox_triage.dedup import deduplicate_emails
from inbox_triage.jmap import JMAPClient
from inbox_triage.train import train_model

load_dotenv()

console = Console()


def _sender(email: dict) -> str:
    from_list = email.get("from") or []
    if from_list:
        return from_list[0].get("email", "unknown")
    return "unknown"


@click.group()
def cli():
    """Inbox triage — classify and archive transactional emails."""


@cli.command()
@click.option("--limit", default=10000, type=int, help="Max emails to sample from archive.")
def train(limit: int):
    """Train the classifier on a random sample of your archived emails."""
    client = JMAPClient()
    console.print(f"Fetching up to {limit} archive emails for training...")
    _pipeline, metrics = train_model(client, limit=limit)

    console.print()
    console.print(f"[bold]Training results[/bold] ({metrics['n_emails']} emails)")
    console.print(
        f"  Keep (flagged):        {metrics['n_keep']}"
    )
    console.print(
        f"  Transactional:         {metrics['n_transactional']}"
    )
    false_archives = metrics["false_archives"]
    false_keeps = metrics["false_keeps"]
    console.print(
        f"  False archives (keep → trans):  {len(false_archives):>3}   ← dangerous"
    )
    console.print(
        f"  False keeps (trans → keep):     {len(false_keeps):>3}   ← harmless"
    )

    all_errors = false_archives + false_keeps
    if all_errors:
        console.print()
        console.print(f"[bold]Misclassified ({len(all_errors)} emails)[/bold]")
        error_table = Table()
        error_table.add_column("Type", style="cyan")
        error_table.add_column("Sender", max_width=30)
        error_table.add_column("Subject", max_width=50)
        for err in false_archives:
            error_table.add_row(
                "[red]false archive[/red]",
                _sender(err["email"]),
                (err["email"].get("subject") or "")[:50],
            )
        for err in false_keeps:
            error_table.add_row(
                "false keep",
                _sender(err["email"]),
                (err["email"].get("subject") or "")[:50],
            )
        console.print(error_table)

    console.print()
    console.print("[green]Model saved to model.joblib[/green]")


@cli.command()
@click.option("--dry-run/--execute", default=True, help="Dry run (default) or execute archiving.")
@click.option("--threshold", default=0.90, type=float, help="Confidence threshold (default: 0.90).")
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
def run(dry_run: bool, threshold: float, limit: int):
    """Classify inbox emails and archive transactional ones."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)
    console.print(f"Fetched {len(emails)} emails. Classifying...")

    results = classify_emails(emails, threshold=threshold)

    # Dedup: among emails NOT being archived, keep only newest per sender+subject
    archive_ids = {r["email"]["id"] for r in results}
    keep_emails = [e for e in emails if e["id"] not in archive_ids]
    _unique, dupes = deduplicate_emails(keep_emails)

    if not results and not dupes:
        console.print("No emails above threshold.")
        return

    if results:
        table = Table(title="Transactional Emails")
        table.add_column("Sender", style="cyan", max_width=35)
        table.add_column("Subject", max_width=50)
        table.add_column("Confidence", justify="right", style="green")

        for r in results:
            table.add_row(
                _sender(r["email"]),
                (r["email"].get("subject") or "")[:50],
                f"{r['probability']:.0%}",
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

    all_archive_ids = [r["email"]["id"] for r in results] + [d["id"] for d in dupes]

    if dry_run:
        console.print(
            f"\n[yellow]{len(results)} transactional + {len(dupes)} duplicates = "
            f"{len(all_archive_ids)} emails would be archived.[/yellow]"
        )
    else:
        archive_id = client.get_mailbox_id("archive")
        client.batch_move(all_archive_ids, archive_id)
        console.print(
            f"\n[green]{len(results)} transactional + {len(dupes)} duplicates = "
            f"{len(all_archive_ids)} emails archived.[/green]"
        )


@cli.command()
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
@click.option("--low", default=0.5, type=float, help="Lower confidence bound (default: 0.5).")
@click.option("--high", default=0.90, type=float, help="Upper confidence bound (default: 0.90).")
def review(limit: int, low: float, high: float):
    """Show uncertain emails and optionally flag them as 'keep'."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)

    results = get_uncertain_emails(emails, low=low, high=high)

    if not results:
        console.print("No uncertain emails found.")
        return

    table = Table(title=f"Uncertain Emails ({low:.0%}-{high:.0%})")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Sender", style="cyan", max_width=35)
    table.add_column("Subject", max_width=50)
    table.add_column("Confidence", justify="right", style="yellow")

    for i, r in enumerate(results):
        table.add_row(
            str(i),
            _sender(r["email"]),
            (r["email"].get("subject") or "")[:50],
            f"{r['probability']:.0%}",
        )

    console.print(table)
    console.print(f"\n{len(results)} uncertain emails.")

    selection = console.input(
        "\n[bold]Flag as keep[/bold] (comma-separated numbers, 'all', or Enter to skip): "
    ).strip()

    if not selection:
        return

    if selection.lower() == "all":
        indices = list(range(len(results)))
    else:
        indices = []
        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                indices.extend(range(int(lo), int(hi) + 1))
            else:
                indices.append(int(part))
        indices = [i for i in indices if 0 <= i < len(results)]

    if not indices:
        console.print("No valid indices.")
        return

    email_ids = [results[i]["email"]["id"] for i in indices]
    client.batch_set_flag(email_ids, flagged=True)
    console.print(f"\n[green]Flagged {len(email_ids)} emails as keep.[/green] Re-train to update the model.")
