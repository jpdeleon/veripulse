"""Scrape command - collect news from various sources."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Source, Article
from veripulse.core.scrapers.news import ScraperFactory, NewspaperScraper, ScrapedArticle
from veripulse.core.analyzers.nlp import Categorizer

app = typer.Typer(
    name="scrape",
    help="Scrape news from configured sources",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available scrape commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Scrape Commands:[/bold cyan]\n")
        console.print("  [green]all[/green]       - Scrape from all enabled sources")
        console.print("  [green]rss[/green]       - Scrape from specific RSS feed")
        console.print("  [green]article[/green]   - Scrape full article content")
        console.print("  [green]sources[/green]   - List configured sources\n")
        console.print("Usage: [dim]veripulse scrape <command> [options][/dim]")
        raise typer.Exit()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def all(
    limit: int = typer.Option(20, "--limit", "-l", help="Max articles per source"),
    topic: str = typer.Option(None, "--topic", "-t", help="Filter by topic"),
):
    """Scrape from all configured RSS and API sources."""
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    session = SessionLocal()

    try:
        scraped_count = 0

        if config.news_sources.get("newsdata", {}).get("enabled"):
            api_scraper = ScraperFactory.get_scraper("newsdata")
            if api_scraper:
                with console.status(f"[bold green]Scraping from NewsData..."):
                    articles = asyncio.run(api_scraper.fetch_articles(topic=topic or "Philippines"))
                scraped_count += save_articles(session, articles)
                console.print(f"[green]NewsData:[/green] {len(articles)} articles")

        if config.news_sources.get("newsapi", {}).get("enabled"):
            api_scraper = ScraperFactory.get_scraper("newsapi")
            if api_scraper:
                with console.status(f"[bold green]Scraping from NewsAPI..."):
                    articles = asyncio.run(api_scraper.fetch_articles(topic=topic or "Philippines"))
                scraped_count += save_articles(session, articles)
                console.print(f"[green]NewsAPI:[/green] {len(articles)} articles")

        rss_config = config.news_sources.get("rss", {})
        if rss_config.get("enabled"):
            rss_scraper = ScraperFactory.get_scraper("rss")
            if rss_scraper:
                for feed in rss_config.get("feeds", []):
                    with console.status(f"[bold green]Scraping {feed['url']}..."):
                        articles = asyncio.run(
                            rss_scraper.fetch_articles(
                                url=feed["url"], category=feed.get("category", "general")
                            )
                        )
                    scraped_count += save_articles(session, articles)
                    console.print(f"[green]RSS:[/green] {len(articles)} from {feed['category']}")

        console.print(f"\n[bold cyan]Total new articles:[/bold cyan] {scraped_count}")

    finally:
        session.close()


@app.command()
def rss(
    url: str = typer.Argument(..., help="RSS feed URL"),
    category: str = typer.Option("general", "--category", "-c", help="Article category"),
):
    """Scrape from a specific RSS feed."""
    scraper = ScraperFactory.get_scraper("rss")
    if not scraper:
        console.print("[red]RSS scraper not available[/red]")
        raise typer.Exit(1)

    with console.status(f"[bold green]Fetching RSS feed..."):
        articles = asyncio.run(scraper.fetch_articles(url=url, category=category))

    _, SessionLocal = init_db(get_config().database.path)
    session = SessionLocal()

    try:
        count = save_articles(session, articles)
        console.print(f"[green]Saved {count} articles[/green]")
    finally:
        session.close()


@app.command()
def article(
    url: str = typer.Argument(..., help="Article URL to scrape"),
    full: bool = typer.Option(False, "--full", "-f", help="Scrape full article content"),
):
    """Scrape a single article's full content."""
    scraper = NewspaperScraper()

    with console.status(f"[bold green]Scraping article..."):
        article = asyncio.run(scraper.scrape_article(url))

    if not article:
        console.print("[red]Failed to scrape article[/red]")
        raise typer.Exit(1)

    _, SessionLocal = init_db(get_config().database.path)
    session = SessionLocal()

    try:
        db_article = save_single_article(session, article, full_content=full)
        if db_article:
            console.print(f"[green]Saved article:[/green] {db_article.title}")
        else:
            console.print("[yellow]Article already exists[/yellow]")
    finally:
        session.close()


@app.command()
def sources():
    """List configured news sources."""
    _, SessionLocal = init_db(get_config().database.path)
    session = SessionLocal()

    try:
        sources = session.query(Source).all()

        table = Table(title="News Sources")
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="magenta")
        table.add_column("Active", style="green")
        table.add_column("Last Scraped")

        for source in sources:
            table.add_row(
                source.name,
                source.category,
                "Yes" if source.is_active else "No",
                source.last_scraped_at.strftime("%Y-%m-%d %H:%M")
                if source.last_scraped_at
                else "Never",
            )

        console.print(table)
    finally:
        session.close()


def save_articles(session: Session, articles: list[ScrapedArticle]) -> int:
    count = 0
    for scraped in articles:
        existing = session.query(Article).filter(Article.url == scraped.url).first()
        if existing:
            continue

        source = session.query(Source).filter(Source.name == scraped.source_name).first()
        if not source:
            source = Source(
                name=scraped.source_name,
                url="",
                category=scraped.source_category,
            )
            session.add(source)
            session.flush()

        article = Article(
            source_id=source.id,
            title=scraped.title,
            url=scraped.url,
            content=scraped.content,
            summary=scraped.summary,
            author=scraped.author,
            published_at=scraped.published_at,
            image_url=scraped.image_url,
        )

        categorizer = Categorizer()
        article.category = categorizer.categorize_from_text(scraped.title, scraped.content or "")

        session.add(article)
        count += 1

    session.commit()
    return count


def save_single_article(
    session: Session, scraped: ScrapedArticle, full_content: bool = False
) -> Article | None:
    existing = session.query(Article).filter(Article.url == scraped.url).first()
    if existing:
        if full_content and scraped.content:
            existing.content = scraped.content
            session.commit()
        return existing

    source = session.query(Source).filter(Source.name == scraped.source_name).first()
    if not source:
        source = Source(
            name=scraped.source_name or "Unknown",
            url="",
            category="general",
        )
        session.add(source)
        session.flush()

    article = Article(
        source_id=source.id,
        title=scraped.title,
        url=scraped.url,
        content=scraped.content if full_content else None,
        summary=scraped.summary,
        author=scraped.author,
        published_at=scraped.published_at,
        image_url=scraped.image_url,
    )

    categorizer = Categorizer()
    article.category = categorizer.categorize_from_text(scraped.title, scraped.content or "")

    session.add(article)
    session.commit()
    session.refresh(article)

    return article
