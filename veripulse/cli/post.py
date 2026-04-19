"""Post command - schedule and post to social media."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, Prompt
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, SocialPost, ArticleStatus
from veripulse.core.publishers.social import PublisherFactory
from veripulse.core.generators.content import LLMClient, SocialPostGenerator


def _get_post_content(session: Session, article: Article, platform: str) -> str:
    """Return post content without calling the LLM when content already exists.

    Priority:
    1. Existing SocialPost draft/scheduled for this article+platform
    2. Commentary or summary + URL (no LLM needed)
    3. LLM generation as last resort
    """
    existing = (
        session.query(SocialPost)
        .filter(SocialPost.article_id == article.id)
        .filter(SocialPost.platform == platform)
        .filter(SocialPost.status.in_(["draft", "scheduled"]))
        .order_by(SocialPost.id.desc())
        .first()
    )
    if existing and existing.content:
        return existing.content

    commentary = article.commentary.commentary_text if article.commentary else ""
    summary = article.summary or commentary or article.title
    url = article.url or ""

    if platform == "twitter":
        base = summary[:230] if summary else article.title
        return f"{base}\n\n{url}" if url else base
    elif platform == "facebook":
        body = commentary or summary
        return f"{body}\n\n🔗 {url}" if url else body

    return summary


def _llm_generate(session: Session, article: Article, platform: str) -> str:
    """Generate content via LLM — only called when no existing content is available."""
    llm = LLMClient()
    generator = SocialPostGenerator(llm)
    commentary = article.commentary.commentary_text if article.commentary else ""
    if platform == "twitter":
        return asyncio.run(generator.generate_tweet(article, commentary))
    elif platform == "facebook":
        return asyncio.run(generator.generate_facebook_post(article, commentary))
    return article.summary or article.title

app = typer.Typer(
    name="post",
    help="Post and schedule social media content",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available post commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Post Commands:[/bold cyan]\n")
        console.print("  [green]schedule[/green] - Schedule a post")
        console.print("  [green]now[/green]      - Post immediately")
        console.print("  [green]pending[/green]  - List scheduled posts")
        console.print("  [green]cancel[/green]   - Cancel scheduled post")
        console.print("  [green]bulk[/green]     - Create posts for approved articles")
        console.print("  [green]test[/green]     - Test social media connection\n")
        console.print("Usage: [dim]veripulse post <command> [options][/dim]")
        raise typer.Exit()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def schedule(
    article_id: int = typer.Argument(..., help="Article ID to schedule"),
    platform: str = typer.Argument(..., help="Platform: twitter, facebook"),
    minutes_from_now: int = typer.Option(30, "--minutes", "-m", help="Minutes from now"),
):
    """Schedule an article for posting."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        if article.status != ArticleStatus.APPROVED.value:
            console.print(f"[red]Article must be approved first[/red]")
            raise typer.Exit(1)

        scheduled_at = datetime.utcnow() + timedelta(minutes=minutes_from_now)

        content = _get_post_content(session, article, platform)
        if not content:
            content = _llm_generate(session, article, platform)

        post = SocialPost(
            article_id=article_id,
            platform=platform,
            content=content,
            scheduled_at=scheduled_at,
            status="scheduled",
        )

        session.add(post)
        article.status = ArticleStatus.SCHEDULED.value
        session.commit()

        console.print(f"[green]✓[/green] Scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"\n[dim]{content}[/dim]")

    finally:
        session.close()


@app.command()
def now(
    article_id: int = typer.Argument(..., help="Article ID to post"),
    platform: str = typer.Argument(..., help="Platform: twitter, facebook"),
):
    """Post immediately to social media."""
    session = get_session()

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            raise typer.Exit(1)

        if not Confirm.ask(f"Post article '{article.title[:40]}...' to {platform}?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

        publisher = PublisherFactory.get_publisher(platform)
        if not publisher:
            console.print(f"[red]Publisher not available: {platform}[/red]")
            raise typer.Exit(1)

        content = _get_post_content(session, article, platform)
        if not content:
            content = _llm_generate(session, article, platform)

        with console.status(f"[bold green]Posting to {platform}..."):
            result = asyncio.run(publisher.post(content, article))

        if result.get("success"):
            post = SocialPost(
                article_id=article_id,
                platform=platform,
                content=content,
                post_url=result.get("post_url"),
                posted_at=datetime.utcnow(),
                status="posted",
            )
            session.add(post)
            article.status = ArticleStatus.POSTED.value
            session.commit()

            console.print(f"[green]✓[/green] Posted successfully")
            console.print(f"[cyan]{result.get('post_url')}[/cyan]")
        else:
            post = SocialPost(
                article_id=article_id,
                platform=platform,
                content=content,
                error_message=result.get("error"),
                status="failed",
            )
            session.add(post)
            session.commit()

            console.print(f"[red]✗[/red] Posting failed: {result.get('error')}")

    finally:
        session.close()


@app.command()
def pending(
    platform: Optional[str] = typer.Option(None, "--platform", help="Filter by platform"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number to show"),
):
    """List pending scheduled posts."""
    session = get_session()

    try:
        query = session.query(SocialPost).filter(SocialPost.status == "scheduled")

        if platform:
            query = query.filter(SocialPost.platform == platform)

        posts = query.order_by(SocialPost.scheduled_at).limit(limit).all()

        if not posts:
            console.print("[yellow]No scheduled posts[/yellow]")
            return

        table = Table(title="Scheduled Posts")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Article", style="white", max_width=35)
        table.add_column("Platform", style="magenta")
        table.add_column("Scheduled", style="yellow")
        table.add_column("Status", style="green")

        for post in posts:
            article = session.query(Article).filter(Article.id == post.article_id).first()
            title = (
                article.title[:32] + "..."
                if article and len(article.title) > 32
                else article.title
                if article
                else "N/A"
            )

            table.add_row(
                str(post.id),
                title,
                post.platform,
                post.scheduled_at.strftime("%Y-%m-%d %H:%M") if post.scheduled_at else "N/A",
                post.status,
            )

        console.print(table)

    finally:
        session.close()


@app.command()
def cancel(
    post_id: int = typer.Argument(..., help="Post ID to cancel"),
):
    """Cancel a scheduled post."""
    session = get_session()

    try:
        post = session.query(SocialPost).filter(SocialPost.id == post_id).first()

        if not post:
            console.print(f"[red]Post {post_id} not found[/red]")
            raise typer.Exit(1)

        if post.status != "scheduled":
            console.print(f"[red]Can only cancel scheduled posts[/red]")
            raise typer.Exit(1)

        post.status = "cancelled"
        session.commit()

        console.print(f"[green]✓[/green] Post {post_id} cancelled")

    finally:
        session.close()


@app.command()
def bulk(
    platform: str = typer.Argument(..., help="Platform: twitter, facebook, all"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max posts to create"),
):
    """Create posts for all approved articles."""
    session = get_session()

    try:
        articles = (
            session.query(Article)
            .filter(Article.status == ArticleStatus.APPROVED.value)
            .order_by(Article.importance_score.desc())
            .limit(limit)
            .all()
        )

        if not articles:
            console.print("[yellow]No approved articles[/yellow]")
            return

        console.print(f"Creating posts for {len(articles)} articles...")

        platforms = ["twitter", "facebook"] if platform == "all" else [platform]

        count = 0
        for article in articles:
            for plat in platforms:
                existing = (
                    session.query(SocialPost)
                    .filter(SocialPost.article_id == article.id)
                    .filter(SocialPost.platform == plat)
                    .first()
                )
                if existing:
                    continue

                content = _get_post_content(session, article, plat)
                if not content:
                    content = _llm_generate(session, article, plat)

                post = SocialPost(
                    article_id=article.id,
                    platform=plat,
                    content=content,
                    status="draft",
                )
                session.add(post)
                count += 1

        session.commit()
        console.print(f"[green]✓[/green] Created {count} draft posts")

    finally:
        session.close()


@app.command()
def test(
    platform: str = typer.Argument(..., help="Platform to test"),
):
    """Test social media connection."""
    publisher = PublisherFactory.get_publisher(platform)

    if not publisher:
        console.print(f"[red]Unknown platform: {platform}[/red]")
        raise typer.Exit(1)

    if not publisher.enabled:
        console.print(f"[red]{platform} integration not enabled[/red]")
        console.print("  Update config.yaml to enable")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] {platform} configured")
