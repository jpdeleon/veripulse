"""DB command - manage database entries."""

from datetime import datetime
from typing import List, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import (
    init_db,
    Article,
    ArticleStatus,
    Commentary,
    SocialPost,
    Source,
)

app = typer.Typer(
    name="db",
    help="Manage database entries",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available db commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse DB Commands:[/bold cyan]\n")
        console.print("  [green]delete[/green]  - Delete articles with optional filters")
        console.print("  [green]stats[/green]   - Show record counts by table and status\n")
        console.print("Usage: [dim]veripulse db <command> [options][/dim]")
        raise typer.Exit(1)


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def delete(
    ids: Optional[List[int]] = typer.Option(None, "--id", help="Delete article by ID (repeatable: --id 1 --id 2)"),
    status: Optional[str] = typer.Option(None, "--status", help=f"Delete articles with this status: {', '.join(s.value for s in ArticleStatus)}"),
    source: Optional[str] = typer.Option(None, "--source", help="Delete articles from this source name (partial match)"),
    before: Optional[str] = typer.Option(None, "--before", help="Delete articles published before date (YYYY-MM-DD)"),
    no_content: bool = typer.Option(False, "--no-content", help="Delete articles with no usable content"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be deleted without deleting"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete articles from the database with optional filters.

    Filters are combined with AND. Related commentary and social posts are
    cascade-deleted automatically.

    \b
    Examples:
      veripulse db delete --id 42
      veripulse db delete --status rejected
      veripulse db delete --source "DuckDuckGo News" --no-content
      veripulse db delete --before 2024-01-01 --dry-run
      veripulse db delete --status raw --no-content -y
    """
    session = get_session()

    if not any([ids, status, source, before, no_content]):
        valid_statuses = ", ".join(s.value for s in ArticleStatus)
        console.print(f"[yellow]Provide at least one filter. See --help.[/yellow]")
        console.print(f"[dim]Valid --status values: {valid_statuses}[/dim]\n")
        articles = (
            session.query(Article)
            .order_by(Article.status, Article.importance_score.desc())
            .limit(20)
            .all()
        )
        if articles:
            hint = Table(title="All articles (pick an ID to delete)")
            hint.add_column("ID", style="cyan", width=4)
            hint.add_column("Status", style="yellow", width=14)
            hint.add_column("Title", style="white", max_width=50)
            hint.add_column("Score", style="green", width=6)
            for a in articles:
                hint.add_row(
                    str(a.id),
                    a.status,
                    a.title[:48] + "..." if len(a.title) > 48 else a.title,
                    f"{a.importance_score:.2f}",
                )
            console.print(hint)
        session.close()
        raise typer.Exit(1)

    try:
        query = session.query(Article)

        if ids:
            query = query.filter(Article.id.in_(ids))

        if status:
            valid = {s.value for s in ArticleStatus}
            if status not in valid:
                console.print(f"[red]Unknown status '{status}'. Valid: {', '.join(sorted(valid))}[/red]")
                raise typer.Exit(1)
            query = query.filter(Article.status == status)

        if source:
            src = session.query(Source).filter(Source.name.ilike(f"%{source}%")).first()
            if not src:
                console.print(f"[yellow]No source matching '{source}' found.[/yellow]")
                return
            query = query.filter(Article.source_id == src.id)

        if before:
            try:
                cutoff = datetime.strptime(before, "%Y-%m-%d")
            except ValueError:
                console.print("[red]--before must be in YYYY-MM-DD format.[/red]")
                raise typer.Exit(1)
            query = query.filter(Article.published_at < cutoff)

        if no_content:
            query = query.filter(
                (Article.content == None)
                | (Article.content == "")
                | (Article.content == "ONLY AVAILABLE IN PAID PLANS")
            )

        articles = query.all()

        if not articles:
            console.print("[yellow]No articles matched the filters.[/yellow]")
            return

        table = Table(title=f"{'[DRY RUN] ' if dry_run else ''}Articles to delete ({len(articles)})")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Status", style="yellow", width=14)
        table.add_column("Source", style="magenta", width=22)
        table.add_column("Published", style="dim", width=12)
        table.add_column("Title", style="white")

        for a in articles[:20]:
            table.add_row(
                str(a.id),
                a.status,
                a.source.name if a.source else "—",
                a.published_at.strftime("%Y-%m-%d") if a.published_at else "—",
                a.title[:60] + "..." if len(a.title) > 60 else a.title,
            )

        console.print(table)
        if len(articles) > 20:
            console.print(f"[dim]  ... and {len(articles) - 20} more[/dim]")

        if dry_run:
            console.print("\n[dim]Dry run — nothing deleted.[/dim]")
            return

        if not yes and not Confirm.ask(f"\nDelete {len(articles)} article(s) and their related records?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

        deleted = 0
        for a in articles:
            session.query(Commentary).filter(Commentary.article_id == a.id).delete()
            session.query(SocialPost).filter(SocialPost.article_id == a.id).delete()
            session.delete(a)
            deleted += 1

        session.commit()
        console.print(f"[green]✓[/green] Deleted {deleted} article(s).")

    finally:
        session.close()


@app.command()
def stats():
    """Show record counts by table and article status."""
    session = get_session()

    try:
        total = session.query(Article).count()

        table = Table(title="Database Stats")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="magenta", justify="right")

        for s in ArticleStatus:
            count = session.query(Article).filter(Article.status == s.value).count()
            if count:
                table.add_row(s.value, str(count))

        table.add_row("─" * 20, "─" * 6)
        table.add_row("[bold]Total articles[/bold]", f"[bold]{total}[/bold]")
        console.print(table)

        console.print(f"  Commentary rows : {session.query(Commentary).count()}")
        console.print(f"  Social posts    : {session.query(SocialPost).count()}")
        console.print(f"  Sources         : {session.query(Source).count()}")

    finally:
        session.close()
