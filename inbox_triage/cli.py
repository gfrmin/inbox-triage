import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from inbox_triage.classify import classify_emails, get_uncertain_emails
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
def train():
    """Train the classifier on your flagged/unflagged inbox emails."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    _pipeline, metrics = train_model(client)

    console.print()
    console.print(f"[bold]Training results[/bold] ({metrics['n_emails']} emails)")
    console.print(
        f"  Keep (flagged):        {metrics['n_keep']}"
    )
    console.print(
        f"  Transactional:         {metrics['n_transactional']}"
    )
    console.print(
        f"  Accuracy:              {metrics['accuracy_mean']:.1%} "
        f"(+/- {metrics['accuracy_std']:.1%})"
    )
    console.print(
        f"  F1 score:              {metrics['f1_mean']:.1%} "
        f"(+/- {metrics['f1_std']:.1%})"
    )
    console.print()
    console.print("[green]Model saved to model.joblib[/green]")


@cli.command()
@click.option("--dry-run/--execute", default=True, help="Dry run (default) or execute archiving.")
@click.option("--threshold", default=0.85, type=float, help="Confidence threshold (default: 0.85).")
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
def run(dry_run: bool, threshold: float, limit: int):
    """Classify inbox emails and archive transactional ones."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)
    console.print(f"Fetched {len(emails)} emails. Classifying...")

    results = classify_emails(emails, threshold=threshold)

    if not results:
        console.print("No emails above threshold.")
        return

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

    if dry_run:
        console.print(f"\n[yellow]{len(results)} emails would be archived.[/yellow]")
    else:
        archive_id = client.get_mailbox_id("archive")
        email_ids = [r["email"]["id"] for r in results]
        client.batch_move(email_ids, archive_id)
        console.print(f"\n[green]{len(results)} emails archived.[/green]")


@cli.command()
@click.option("--limit", default=500, type=int, help="Max emails to fetch.")
def review(limit: int):
    """Show emails in the uncertain zone (0.5-0.85 confidence)."""
    client = JMAPClient()
    console.print("Fetching inbox emails...")
    emails = client.get_inbox_emails(limit=limit)

    results = get_uncertain_emails(emails)

    if not results:
        console.print("No uncertain emails found.")
        return

    table = Table(title="Uncertain Emails (0.5-0.85)")
    table.add_column("Sender", style="cyan", max_width=35)
    table.add_column("Subject", max_width=50)
    table.add_column("Confidence", justify="right", style="yellow")

    for r in results:
        table.add_row(
            _sender(r["email"]),
            (r["email"].get("subject") or "")[:50],
            f"{r['probability']:.0%}",
        )

    console.print(table)
    console.print(f"\n{len(results)} uncertain emails. Consider flagging important ones and re-training.")
