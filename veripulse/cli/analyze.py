"""Analyze command - categorize, sentiment, importance scoring."""

from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, ArticleStatus
from veripulse.core.analyzers.nlp import (
    Categorizer,
    SentimentAnalyzer,
    ImportanceScorer,
    TrendingDetector,
)

app = typer.Typer(
    name="analyze",
    help="Analyze articles for category, sentiment, and importance",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available analyze commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Analyze Commands:[/bold cyan]\n")
        console.print("  [green]all[/green]       - Analyze all raw articles")
        console.print("  [green]single[/green]   - Analyze a single article")
        console.print("  [green]list[/green]     - List analyzed articles")
        console.print("  [green]stats[/green]    - Show analysis statistics\n")
        console.print("Usage: [dim]veripulse analyze <command> [options][/dim]")
        raise typer.Exit()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


def _article_hint(session: Session, statuses: list, limit: int = 10) -> None:
    """Print a compact article table to help the user pick an ID."""
    articles = (
        session.query(Article)
        .filter(Article.status.in_(statuses))
        .order_by(Article.importance_score.desc())
        .limit(limit)
        .all()
    )
    if not articles:
        return
    table = Table(title=f"Available articles  [{', '.join(statuses)}]")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Title", style="white", max_width=52)
    table.add_column("Category", style="magenta")
    table.add_column("Score", style="green", width=6)
    for a in articles:
        table.add_row(
            str(a.id),
            a.title[:50] + "..." if len(a.title) > 50 else a.title,
            a.category or "—",
            f"{a.importance_score:.2f}",
        )
    console.print(table)


@app.command()
def all(
    limit: int = typer.Option(50, "--limit", "-l", help="Number of articles to analyze"),
):
    """Analyze all raw articles."""
    session = get_session()

    try:
        articles = (
            session.query(Article)
            .filter(Article.status == ArticleStatus.RAW.value)
            .limit(limit)
            .all()
        )

        if not articles:
            console.print("[yellow]No raw articles to analyze[/yellow]")
            return

        categorizer = Categorizer()
        sentiment_analyzer = SentimentAnalyzer()
        importance_scorer = ImportanceScorer()
        trending_detector = TrendingDetector()

        with Progress() as progress:
            task = progress.add_task("[cyan]Analyzing articles...", total=len(articles))

            for article in articles:
                progress.print(f"[dim][{article.id}][/dim] {article.title[:70]}")
                all_articles = session.query(Article).all()

                article.category = categorizer.categorize(article)

                sentiment, score = sentiment_analyzer.analyze_article(article)
                article.sentiment = sentiment
                article.sentiment_score = score

                article.importance_score = importance_scorer.calculate(article, all_articles)
                article.trending_score = trending_detector.calculate_trending_score(
                    article, all_articles
                )

                article.status = ArticleStatus.ANALYZED.value

                progress.print(
                    f"  [green]✓[/green] {article.category or '—'} | "
                    f"{article.sentiment or '—'} | importance: {article.importance_score:.2f}"
                )
                progress.advance(task)

        session.commit()
        console.print(f"[green]✓[/green] Analyzed {len(articles)} articles")

    finally:
        session.close()


@app.command()
def single(
    article_id: Optional[int] = typer.Argument(None, help="Article ID to analyze"),
):
    """Analyze a single article."""
    session = get_session()

    if article_id is None:
        _article_hint(session, [ArticleStatus.RAW.value])
        session.close()
        raise typer.Exit(1)

    try:
        article = session.query(Article).filter(Article.id == article_id).first()

        if not article:
            console.print(f"[red]Article {article_id} not found[/red]")
            _article_hint(session, [ArticleStatus.RAW.value])
            raise typer.Exit(1)

        categorizer = Categorizer()
        sentiment_analyzer = SentimentAnalyzer()
        importance_scorer = ImportanceScorer()
        trending_detector = TrendingDetector()

        all_articles = session.query(Article).all()

        article.category = categorizer.categorize(article)
        sentiment, score = sentiment_analyzer.analyze_article(article)
        article.sentiment = sentiment
        article.sentiment_score = score
        article.importance_score = importance_scorer.calculate(article, all_articles)
        article.trending_score = trending_detector.calculate_trending_score(article, all_articles)
        article.status = ArticleStatus.ANALYZED.value

        session.commit()

        console.print(f"[green]✓[/green] Analyzed article {article_id}")
        console.print(f"  Category:   {article.category or '—'}")
        console.print(f"  Sentiment:  {article.sentiment or '—'} ({article.sentiment_score:.2f})")
        console.print(f"  Importance: {article.importance_score:.2f}")
        console.print(f"  Trending:   {article.trending_score:.2f}")

    finally:
        session.close()


@app.command()
def list(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    sentiment: str = typer.Option(None, "--sentiment", "-s", help="Filter by sentiment"),
    sort_by: str = typer.Option("importance", "--sort", help="Sort by: importance, trending, date"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number to show"),
):
    """List analyzed articles."""
    session = get_session()

    try:
        query = session.query(Article).filter(Article.status == ArticleStatus.ANALYZED.value)

        if category:
            query = query.filter(Article.category == category)
        if sentiment:
            query = query.filter(Article.sentiment == sentiment)

        sort_column = {
            "importance": Article.importance_score,
            "trending": Article.trending_score,
            "date": Article.published_at,
        }.get(sort_by, Article.importance_score)

        articles = query.order_by(sort_column.desc()).limit(limit).all()

        if not articles:
            console.print("[yellow]No analyzed articles found[/yellow]")
            return

        table = Table(title="Analyzed Articles")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("Category", style="magenta")
        table.add_column("Sentiment", style="yellow")
        table.add_column("Importance", style="green")

        for article in articles:
            table.add_row(
                str(article.id),
                article.title[:48] + "..." if len(article.title) > 48 else article.title,
                article.category or "N/A",
                article.sentiment or "N/A",
                f"{article.importance_score:.2f}",
            )

        console.print(table)

    finally:
        session.close()


@app.command()
def stats():
    """Show analysis statistics."""
    session = get_session()

    try:
        total = session.query(Article).count()
        by_status = {}
        for status in ArticleStatus:
            count = session.query(Article).filter(Article.status == status.value).count()
            by_status[status.value] = count

        by_category = {}
        categories = session.query(Article.category).distinct().all()
        for (cat,) in categories:
            if cat:
                count = session.query(Article).filter(Article.category == cat).count()
                by_category[cat] = count

        by_sentiment = {}
        for sentiment in ["positive", "negative", "neutral", "mixed"]:
            count = session.query(Article).filter(Article.sentiment == sentiment).count()
            by_sentiment[sentiment] = count

        console.print("\n[bold cyan]Article Statistics[/bold cyan]\n")
        console.print(f"Total articles: {total}")
        console.print("\nBy Status:")
        for status, count in by_status.items():
            console.print(f"  {status}: {count}")

        console.print("\nBy Category:")
        for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {cat}: {count}")

        console.print("\nBy Sentiment:")
        for sent, count in by_sentiment.items():
            console.print(f"  {sent}: {count}")

    finally:
        session.close()
