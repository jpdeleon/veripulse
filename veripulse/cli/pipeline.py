"""Pipeline command - chain analyze → summarize → commentary for one or more articles."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, ArticleStatus, Commentary
from veripulse.core.analyzers.nlp import Categorizer, SentimentAnalyzer, ImportanceScorer, TrendingDetector
from veripulse.core.generators.content import LLMClient, Summarizer, Commentator

app = typer.Typer(
    name="pipeline",
    help="Run the full analysis and generation pipeline",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available pipeline commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Pipeline Commands:[/bold cyan]\n")
        console.print("  [green]run[/green]      - Run full pipeline on one or all pending articles")
        console.print("\nUsage: [dim]veripulse pipeline run [article_id] [options][/dim]")
        raise typer.Exit(1)


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


def _step(label: str):
    console.print(f"\n[bold cyan]▶ {label}[/bold cyan]")


def _ok(msg: str):
    console.print(f"  [green]✓[/green] {msg}")


def _skip(msg: str):
    console.print(f"  [dim]–[/dim] {msg}")


def _fail(msg: str):
    console.print(f"  [red]✗[/red] {msg}")


def _run_article(session: Session, article: Article, llm: LLMClient, bilingual: bool, filipino: bool) -> bool:
    """Run analyze → summary → commentary for a single article. Returns True on success."""
    console.print(
        Panel.fit(
            f"[bold]{article.title[:70]}[/bold]\n[dim]ID {article.id} · {article.status}[/dim]",
            border_style="cyan",
        )
    )

    # --- Analyze ---
    _step("Analyze")
    if article.status == ArticleStatus.RAW.value:
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
        _ok(
            f"{article.category or '—'} | {article.sentiment or '—'} | "
            f"importance: {article.importance_score:.2f}"
        )
    else:
        _skip(f"Already {article.status}, skipping analyze")

    # --- Summary ---
    _step("Generate Summary")
    if article.status == ArticleStatus.ANALYZED.value:
        if not article.content:
            _fail("No content — run `veripulse scrape enrich` first")
            return False
        summarizer = Summarizer(llm)
        if bilingual:
            summary = asyncio.run(summarizer.summarize_bilingual(article))
        else:
            summary = asyncio.run(summarizer.summarize(article))
        article.summary = summary
        article.status = ArticleStatus.GENERATED.value
        session.commit()
        _ok(f"{summary[:120]}...")
    else:
        _skip(f"Already {article.status}, skipping summary")

    # --- Commentary ---
    _step("Generate Commentary")
    if article.status == ArticleStatus.GENERATED.value:
        commentator = Commentator(llm)
        if filipino:
            result = asyncio.run(commentator.generate_commentary_filipino(article))
        else:
            result = asyncio.run(commentator.generate_commentary(article))

        commentary = Commentary(
            article_id=article.id,
            headline=result.get("headline"),
            commentary_text=result.get("commentary", ""),
            key_takeaways=", ".join(result.get("key_takeaways", [])) if result.get("key_takeaways") else None,
            bias_score=result.get("bias_score"),
            fact_check_notes=result.get("bias_notes"),
            language="fil" if filipino else "en",
        )
        existing = session.query(Commentary).filter(Commentary.article_id == article.id).first()
        if existing:
            existing.headline = commentary.headline
            existing.commentary_text = commentary.commentary_text
            existing.key_takeaways = commentary.key_takeaways
            existing.bias_score = commentary.bias_score
        else:
            session.add(commentary)

        article.status = ArticleStatus.PENDING_REVIEW.value
        session.commit()
        headline = result.get("headline", "")
        _ok(headline[:100] if headline else "Commentary generated")
    else:
        _skip(f"Already {article.status}, skipping commentary")

    console.print(f"\n[green]✓[/green] Article {article.id} → [bold]{article.status}[/bold]")
    return True


@app.command()
def run(
    target: Optional[str] = typer.Argument(None, help="Article ID or URL to process (omit for all pending)"),
    bilingual: bool = typer.Option(False, "--bilingual", help="Generate bilingual summary"),
    filipino: bool = typer.Option(False, "--filipino", help="Generate commentary in Filipino"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max articles when processing all"),
):
    """Run full pipeline (analyze → summary → commentary) on an article or all pending articles."""
    session = get_session()

    try:
        llm = LLMClient()
        if not llm.check_connection():
            console.print("[red]Cannot connect to Ollama.[/red]")
            console.print(f"[dim]Expected at: {llm.base_url}  Model: {llm.model}[/dim]")
            raise typer.Exit(1)

        if target:
            is_url = target.startswith("http://") or target.startswith("https://")
            if is_url:
                article = session.query(Article).filter(Article.url == target).first()
                if not article:
                    console.print(f"[red]No article found with URL: {target}[/red]")
                    console.print("[dim]Tip: run `veripulse scrape article <url> --full` first[/dim]")
                    raise typer.Exit(1)
            else:
                try:
                    article_id = int(target)
                except ValueError:
                    console.print(f"[red]Invalid target '{target}': must be an article ID or a URL[/red]")
                    raise typer.Exit(1)
                article = session.query(Article).filter(Article.id == article_id).first()
                if not article:
                    console.print(f"[red]Article {article_id} not found[/red]")
                    raise typer.Exit(1)
            articles = [article]
        else:
            articles = (
                session.query(Article)
                .filter(Article.status.in_([
                    ArticleStatus.RAW.value,
                    ArticleStatus.ANALYZED.value,
                    ArticleStatus.GENERATED.value,
                ]))
                .filter(Article.content != None)
                .filter(Article.content != "")
                .filter(Article.content != "ONLY AVAILABLE IN PAID PLANS")
                .order_by(Article.importance_score.desc())
                .limit(limit)
                .all()
            )
            if not articles:
                console.print("[yellow]No articles pending pipeline processing[/yellow]")
                return

        ok = 0
        for article in articles:
            if _run_article(session, article, llm, bilingual, filipino):
                ok += 1

        if len(articles) > 1:
            console.print(f"\n[bold cyan]Pipeline complete:[/bold cyan] {ok}/{len(articles)} articles processed")

    finally:
        session.close()
