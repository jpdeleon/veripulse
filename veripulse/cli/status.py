"""Status command - system status and monitoring."""

import typer
import click
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from sqlalchemy import func
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, SocialPost, ArticleStatus
from veripulse.core.generators.content import LLMClient

STATUS_CHOICES = [s.value for s in ArticleStatus]

app = typer.Typer(
    name="status",
    help="Show system status and statistics",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available status commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Status Commands:[/bold cyan]\n")
        console.print("  [green]main[/green]      - Show overall system status")
        console.print("  [green]articles[/green]  - List recent articles")
        console.print("  [green]queue[/green]    - Show pending work queue")
        console.print("  [green]top[/green]      - Show top articles by importance\n")
        console.print("Usage: [dim]veripulse status <command> [options][/dim]")
        raise typer.Exit()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def main():
    """Show overall system status."""
    session = get_session()

    try:
        config = get_config()

        console.print(
            Panel.fit(
                f"[bold cyan]Veripulse Status[/bold cyan]\nDatabase: {config.database.path}",
                border_style="cyan",
            )
        )

        total_articles = session.query(Article).count()
        total_posts = session.query(SocialPost).count()

        status_counts = {}
        for status in ArticleStatus:
            count = session.query(Article).filter(Article.status == status.value).count()
            status_counts[status.value] = count

        scheduled = session.query(SocialPost).filter(SocialPost.status == "scheduled").count()
        posted = session.query(SocialPost).filter(SocialPost.status == "posted").count()

        console.print(f"\n[bold]Articles:[/bold] {total_articles}")
        for status, count in status_counts.items():
            if count > 0:
                console.print(f"  {status}: {count}")

        console.print(f"\n[bold]Social Posts:[/bold] {total_posts}")
        console.print(f"  scheduled: {scheduled}")
        console.print(f"  posted: {posted}")

        recent = session.query(Article).order_by(Article.created_at.desc()).limit(5).all()

        if recent:
            console.print("\n[bold]Recent Articles:[/bold]")
            for article in recent:
                age = datetime.utcnow() - article.created_at
                age_str = f"{age.seconds // 60}m ago" if age.days == 0 else f"{age.days}d ago"
                console.print(f"  [{article.id}] {article.title[:50]}... [{age_str}]")

        llm = LLMClient()
        if llm.check_connection():
            console.print(f"\n[green]✓[/green] Ollama: Connected ({llm.model})")
        else:
            console.print(f"\n[red]✗[/red] Ollama: Not connected")
            console.print("  Run: ollama serve")

    finally:
        session.close()


@app.command()
def articles(
    limit: int = typer.Option(10, "--limit", "-l", help="Number to show"),
    status: str = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status",
        click_type=click.Choice(STATUS_CHOICES, case_sensitive=False),
    ),
):
    """List recent articles."""
    session = get_session()

    try:
        query = session.query(Article).order_by(Article.created_at.desc())

        if status:
            query = query.filter(Article.status == status)

        articles = query.limit(limit).all()

        if not articles:
            console.print("[yellow]No articles found[/yellow]")
            return

        table = Table(title="Recent Articles")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("Status", style="yellow")
        table.add_column("Category", style="magenta")

        for article in articles:
            table.add_row(
                str(article.id),
                article.title[:47] + "..." if len(article.title) > 47 else article.title,
                article.status,
                article.category or "N/A",
            )

        console.print(table)

    finally:
        session.close()


@app.command()
def queue():
    """Show pending work queue."""
    session = get_session()

    try:
        raw_count = session.query(Article).filter(Article.status == ArticleStatus.RAW.value).count()
        analyzed_count = (
            session.query(Article).filter(Article.status == ArticleStatus.ANALYZED.value).count()
        )
        pending_review = (
            session.query(Article)
            .filter(Article.status == ArticleStatus.PENDING_REVIEW.value)
            .count()
        )
        approved = (
            session.query(Article).filter(Article.status == ArticleStatus.APPROVED.value).count()
        )

        scheduled_posts = (
            session.query(SocialPost)
            .filter(SocialPost.status == "scheduled")
            .order_by(SocialPost.scheduled_at)
            .limit(5)
            .all()
        )

        console.print(
            Panel.fit(
                "[bold]Work Queue[/bold]\n\n"
                f"Raw articles: [cyan]{raw_count}[/cyan]\n"
                f"Need analysis: [yellow]{analyzed_count}[/yellow]\n"
                f"Pending review: [magenta]{pending_review}[/magenta]\n"
                f"Approved: [green]{approved}[/green]",
                border_style="cyan",
            )
        )

        if scheduled_posts:
            console.print("\n[bold]Upcoming Posts:[/bold]")
            for post in scheduled_posts:
                article = session.query(Article).filter(Article.id == post.article_id).first()
                console.print(
                    f"  {post.scheduled_at.strftime('%H:%M')} - "
                    f"{post.platform} - "
                    f"{article.title[:40]}..."
                    if article
                    else "Unknown"
                )

    finally:
        session.close()


@app.command()
def top(
    limit: int = typer.Option(10, "--limit", "-l", help="Number to show"),
):
    """Show top articles by importance."""
    session = get_session()

    try:
        articles = (
            session.query(Article)
            .filter(Article.status != ArticleStatus.RAW.value)
            .order_by(Article.importance_score.desc())
            .limit(limit)
            .all()
        )

        if not articles:
            console.print("[yellow]No ranked articles[/yellow]")
            return

        table = Table(title="Top Articles by Importance")
        table.add_column("Rank", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=45)
        table.add_column("Importance", style="green")
        table.add_column("Category", style="magenta")

        for i, article in enumerate(articles, 1):
            bar = "█" * int(article.importance_score * 10)
            table.add_row(
                str(i),
                article.title[:42] + "..." if len(article.title) > 42 else article.title,
                f"{article.importance_score:.2f} {bar}",
                article.category or "N/A",
            )

        console.print(table)

    finally:
        session.close()
