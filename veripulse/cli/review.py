"""Review command - human review and approval workflow."""

from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, Commentary, ArticleStatus

app = typer.Typer(
    name="review",
    help="Review and approve articles before posting",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available review commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Review Commands:[/bold cyan]\n")
        console.print("  [green]list[/green]     - List articles for review")
        console.print("  [green]show[/green]    - Show article details")
        console.print("  [green]approve[/green] - Approve article for posting")
        console.print("  [green]reject[/green]  - Reject article")
        console.print("  [green]edit[/green]    - Edit article field")
        console.print("  [green]bulk[/green]    - Bulk approve/reject\n")
        console.print("Usage: [dim]veripulse review <command> [options][/dim]")
        raise typer.Exit()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def list(
    status: str = typer.Option("pending_review", "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number to show"),
):
    """List articles for review."""
    session = get_session()

    try:
        articles = (
            session.query(Article)
            .filter(Article.status == status)
            .order_by(Article.importance_score.desc())
            .limit(limit)
            .all()
        )

        if not articles:
            console.print(f"[yellow]No articles with status: {status}[/yellow]")
            return

        table = Table(title=f"Articles - {status}")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=45)
        table.add_column("Category", style="magenta")
        table.add_column("Importance", style="green")
        table.add_column("Source", style="yellow")

        for article in articles:
            table.add_row(
                str(article.id),
                article.title[:42] + "..." if len(article.title) > 42 else article.title,
                article.category or "N/A",
                f"{article.importance_score:.2f}",
                article.source.name if article.source else "N/A",
            )

        console.print(table)

    finally:
        session.close()


@app.command()
def show(
    article_id: int = typer.Argument(..., help="Article ID to review"),
):
    """Show full article details for review."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        commentary = session.query(Commentary).filter(Commentary.article_id == article_id).first()

        console.print(f"\n[bold cyan]Article #{article.id}[/bold cyan]")
        console.print(f"[bold]{article.title}[/bold]\n")

        console.print(f"[yellow]Status:[/yellow] {article.status}")
        console.print(f"[yellow]Category:[/yellow] {article.category}")
        console.print(
            f"[yellow]Sentiment:[/yellow] {article.sentiment} ({article.sentiment_score})"
        )
        console.print(f"[yellow]Importance:[/yellow] {article.importance_score:.2f}")
        console.print(f"[yellow]Trending:[/yellow] {article.trending_score:.2f}")
        console.print(
            f"[yellow]Source:[/yellow] {article.source.name if article.source else 'Unknown'}"
        )
        console.print(f"[yellow]URL:[/yellow] {article.url}")
        console.print(f"[yellow]Published:[/yellow] {article.published_at}")

        if article.summary:
            console.print(f"\n[bold green]Summary:[/bold green]")
            console.print(f"  {article.summary}")

        if article.content:
            console.print(f"\n[bold green]Content Preview:[/bold green]")
            console.print(f"  {article.content[:500]}...")

        if commentary:
            console.print(f"\n[bold green]Commentary:[/bold green]")
            if commentary.headline:
                console.print(f"  [bold]Headline:[/bold] {commentary.headline}")
            console.print(f"  {commentary.commentary_text}")
            if commentary.key_takeaways:
                console.print(f"\n  [bold]Key Takeaways:[/bold]")
                for kt in commentary.key_takeaways.split(", "):
                    console.print(f"    - {kt}")
            if commentary.bias_score:
                console.print(f"\n  [bold]Bias Score:[/bold] {commentary.bias_score:.2f}")
        else:
            console.print(f"\n[dim]No commentary generated yet[/dim]")

    finally:
        session.close()


@app.command()
def approve(
    article_id: int = typer.Argument(..., help="Article ID to approve"),
):
    """Approve an article for posting."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        if not Confirm.ask(f"Approve article '{article.title[:50]}...'?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

        article.status = ArticleStatus.APPROVED.value
        session.commit()

        console.print(f"[green]✓[/green] Article {article_id} approved")

    finally:
        session.close()


@app.command()
def reject(
    article_id: int = typer.Argument(..., help="Article ID to reject"),
    reason: Optional[str] = typer.Option(None, "--reason", "-r", help="Rejection reason"),
):
    """Reject an article."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        if not reason:
            reason = Prompt.ask("Rejection reason")

        article.status = ArticleStatus.REJECTED.value
        session.commit()

        console.print(f"[red]✗[/red] Article {article_id} rejected: {reason}")

    finally:
        session.close()


@app.command()
def edit(
    article_id: int = typer.Argument(..., help="Article ID to edit"),
    field: str = typer.Argument(..., help="Field to edit: summary, headline, commentary"),
):
    """Edit article field before posting."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        new_value = Prompt.ask(f"New {field}")

        if field == "summary":
            article.summary = new_value
        elif field == "headline":
            commentary = (
                session.query(Commentary).filter(Commentary.article_id == article_id).first()
            )
            if commentary:
                commentary.headline = new_value
            else:
                console.print("[yellow]No commentary exists to edit headline[/yellow]")
                return
        elif field == "commentary":
            commentary = (
                session.query(Commentary).filter(Commentary.article_id == article_id).first()
            )
            if commentary:
                commentary.commentary_text = new_value
            else:
                console.print("[yellow]No commentary exists to edit[/yellow]")
                return
        else:
            console.print(f"[red]Unknown field: {field}[/red]")
            console.print("Available fields: summary, headline, commentary")
            return

        session.commit()
        console.print(f"[green]✓[/green] Updated {field}")

    finally:
        session.close()


@app.command()
def bulk(
    action: str = typer.Argument(..., help="Action: approve, reject"),
    min_importance: float = typer.Option(0.5, "--min", help="Minimum importance score"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter by category"),
):
    """Bulk approve or reject articles."""
    session = get_session()

    try:
        query = session.query(Article).filter(Article.status == ArticleStatus.PENDING_REVIEW.value)
        query = query.filter(Article.importance_score >= min_importance)

        if category:
            query = query.filter(Article.category == category)

        articles = query.all()

        if not articles:
            console.print("[yellow]No articles match criteria[/yellow]")
            return

        console.print(f"Found {len(articles)} articles to {action}")

        if not Confirm.ask(f"Proceed with bulk {action}?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

        for article in articles:
            article.status = (
                ArticleStatus.APPROVED.value
                if action == "approve"
                else ArticleStatus.REJECTED.value
            )

        session.commit()
        console.print(f"[green]✓[/green] Bulk {action} completed: {len(articles)} articles")

    finally:
        session.close()
