"""Status command - system status and monitoring."""

from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy.orm import Session

import httpx

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, ArticleStatus, SocialPost

app = typer.Typer(
    name="status",
    help="Show system status and statistics",
    invoke_without_command=True,
)
console = Console()

STATUS_CHOICES = [s.value for s in ArticleStatus]


@app.callback()
def callback(ctx: typer.Context):
    """Show available status commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Status Commands:[/bold cyan]\n")
        console.print("  [green]main[/green]      - Show overall system status")
        console.print("  [green]articles[/green]  - List recent articles")
        console.print("  [green]queue[/green]     - Show pending work queue")
        console.print("  [green]top[/green]       - Show top articles by importance\n")
        console.print("Usage: [dim]veripulse status <command> [options][/dim]")
        raise typer.Exit(1)


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

        status_counts = {
            s.value: session.query(Article).filter(Article.status == s.value).count()
            for s in ArticleStatus
        }

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

        config = get_config()
        llm_cfg = config.llm
        if llm_cfg.host:
            console.print(f"\n[cyan]~[/cyan] Ollama: Remote via SSH ({llm_cfg.host}) — model: {llm_cfg.model}")
            console.print("  [dim]Run: veripulse generate check  (opens tunnel to verify)[/dim]")
        else:
            import httpx
            try:
                resp = httpx.get(f"{llm_cfg.base_url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    console.print(f"\n[green]✓[/green] Ollama: Connected at {llm_cfg.base_url} ({llm_cfg.model})")
                else:
                    console.print(f"\n[red]✗[/red] Ollama: Unexpected response ({resp.status_code})")
            except Exception:
                console.print(f"\n[red]✗[/red] Ollama: Not reachable at {llm_cfg.base_url}")
                console.print("  [dim]Run: ollama serve[/dim]")

    finally:
        session.close()


@app.command()
def articles(
    limit: int = typer.Option(10, "--limit", "-l", help="Number to show"),
    status: Optional[str] = typer.Option(
        None, "--status", "-s",
        help=f"Filter by status ({', '.join(STATUS_CHOICES)})",
    ),
):
    """List recent articles."""
    session = get_session()

    try:
        if status and status not in STATUS_CHOICES:
            console.print(f"[red]Unknown status '{status}'. Valid: {', '.join(STATUS_CHOICES)}[/red]")
            raise typer.Exit(1)

        query = session.query(Article).order_by(Article.created_at.desc())
        if status:
            query = query.filter(Article.status == status)

        results = query.limit(limit).all()

        if not results:
            console.print("[yellow]No articles found[/yellow]")
            return

        table = Table(title="Recent Articles")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("Status", style="yellow")
        table.add_column("Category", style="magenta")
        table.add_column("Published", style="dim")

        for article in results:
            pub = article.published_at.strftime("%Y-%m-%d") if article.published_at else "—"
            table.add_row(
                str(article.id),
                article.title[:47] + "..." if len(article.title) > 47 else article.title,
                article.status,
                article.category or "—",
                pub,
            )

        console.print(table)

    finally:
        session.close()


@app.command()
def queue():
    """Show pending work queue."""
    session = get_session()

    try:
        raw = session.query(Article).filter(Article.status == ArticleStatus.RAW.value).count()
        analyzed = session.query(Article).filter(Article.status == ArticleStatus.ANALYZED.value).count()
        pending = session.query(Article).filter(Article.status == ArticleStatus.PENDING_REVIEW.value).count()
        approved = session.query(Article).filter(Article.status == ArticleStatus.APPROVED.value).count()

        console.print(
            Panel.fit(
                "[bold]Work Queue[/bold]\n\n"
                f"Raw (needs analysis):     [cyan]{raw}[/cyan]\n"
                f"Analyzed (needs gen):     [yellow]{analyzed}[/yellow]\n"
                f"Pending review:           [magenta]{pending}[/magenta]\n"
                f"Approved (ready to post): [green]{approved}[/green]",
                border_style="cyan",
            )
        )

        if raw:
            console.print("[dim]  → veripulse analyze all[/dim]")
        if analyzed:
            console.print("[dim]  → veripulse generate summary --pending[/dim]")
        if pending:
            console.print("[dim]  → veripulse review list[/dim]")
        if approved:
            console.print("[dim]  → veripulse post bulk facebook[/dim]")

        scheduled_posts = (
            session.query(SocialPost)
            .filter(SocialPost.status == "scheduled")
            .order_by(SocialPost.scheduled_at)
            .limit(5)
            .all()
        )

        if scheduled_posts:
            console.print("\n[bold]Upcoming Posts:[/bold]")
            for post in scheduled_posts:
                article = session.query(Article).filter(Article.id == post.article_id).first()
                title = article.title[:40] if article else "Unknown"
                time_str = post.scheduled_at.strftime("%H:%M") if post.scheduled_at else "?"
                console.print(f"  {time_str} [{post.platform}] {title}")

    finally:
        session.close()


@app.command()
def top(
    limit: int = typer.Option(10, "--limit", "-l", help="Number to show"),
):
    """Show top articles by importance score."""
    session = get_session()

    try:
        results = (
            session.query(Article)
            .filter(Article.status != ArticleStatus.RAW.value)
            .order_by(Article.importance_score.desc())
            .limit(limit)
            .all()
        )

        if not results:
            console.print("[yellow]No ranked articles found[/yellow]")
            return

        table = Table(title="Top Articles by Importance")
        table.add_column("Rank", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=48)
        table.add_column("Score", style="green", width=12)
        table.add_column("Category", style="magenta")
        table.add_column("Status", style="yellow")

        for i, article in enumerate(results, 1):
            bar = "█" * int(article.importance_score * 10)
            table.add_row(
                str(i),
                article.title[:45] + "..." if len(article.title) > 45 else article.title,
                f"{article.importance_score:.2f} {bar}",
                article.category or "—",
                article.status,
            )

        console.print(table)

    finally:
        session.close()
