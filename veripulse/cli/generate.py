"""Generate command - create summaries, commentary, and social posts."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from sqlalchemy.orm import Session

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, ArticleStatus, Commentary
from veripulse.core.generators.content import (
    LLMClient,
    Summarizer,
    Commentator,
    SocialPostGenerator,
)
from veripulse.core.logging import setup_logging

app = typer.Typer(
    name="generate",
    help="Generate summaries, commentary, and social posts",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def callback(ctx: typer.Context):
    """Show available generate commands."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Veripulse Generate Commands:[/bold cyan]\n")
        console.print("  [green]summary[/green]     - Generate article summaries")
        console.print("  [green]commentary[/green]   - Generate commentary")
        console.print("  [green]social[/green]       - Generate social media posts")
        console.print("  [green]check[/green]        - Check Ollama connection\n")
        console.print("Usage: [dim]veripulse generate <command> [options][/dim]")
        raise typer.Exit()


setup_logging()


def get_session() -> Session:
    config = get_config()
    _, SessionLocal = init_db(config.database.path)
    return SessionLocal()


@app.command()
def summary(
    article_id: Optional[int] = typer.Argument(None, help="Article ID (or use --pending)"),
    pending: bool = typer.Option(False, "--pending", help="Generate for all pending articles"),
    bilingual: bool = typer.Option(False, "--bilingual", help="Generate bilingual summary"),
):
    """Generate article summary."""
    session = get_session()

    try:
        llm = LLMClient()
        if not llm.check_connection():
            console.print("[red]Cannot connect to Ollama.[/red]")
            console.print(f"[yellow]Make sure Ollama is running: `ollama serve`[/yellow]")
            console.print(f"[dim]Expected at: {llm.base_url}[/dim]")
            console.print(f"[dim]Model: {llm.model}[/dim]")
            raise typer.Exit(1)

        summarizer = Summarizer(llm)

        if pending:
            articles = (
                session.query(Article)
                .filter(Article.status == ArticleStatus.ANALYZED.value)
                .filter(Article.content != None)
                .limit(10)
                .all()
            )
        elif article_id:
            articles = [session.query(Article).filter(Article.id == article_id).first()]
        else:
            console.print("[yellow]Provide article_id or use --pending[/yellow]")
            raise typer.Exit(1)

        articles = [a for a in articles if a]

        if not articles:
            console.print("[yellow]No articles to summarize[/yellow]")
            return

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating summaries...", total=len(articles))

            for article in articles:
                if bilingual:
                    summary = asyncio.run(summarizer.summarize_bilingual(article))
                else:
                    summary = asyncio.run(summarizer.summarize(article))

                article.summary = summary
                article.status = ArticleStatus.GENERATED.value
                session.commit()

                console.print(f"\n[green]Summary for {article.id}:[/green]")
                console.print(f"  {summary[:200]}...")

                progress.advance(task)

        console.print(f"\n[cyan]Generated {len(articles)} summaries[/cyan]")

    finally:
        session.close()


@app.command()
def commentary(
    article_id: Optional[int] = typer.Argument(None, help="Article ID"),
    pending: bool = typer.Option(False, "--pending", help="Generate for pending articles"),
    filipino: bool = typer.Option(False, "--filipino", help="Generate in Filipino"),
):
    """Generate insightful commentary."""
    session = get_session()

    try:
        llm = LLMClient()
        if not llm.check_connection():
            console.print("[red]Cannot connect to Ollama.[/red]")
            console.print(f"[yellow]Make sure Ollama is running: `ollama serve`[/yellow]")
            console.print(f"[dim]Expected at: {llm.base_url}[/dim]")
            console.print(f"[dim]Model: {llm.model}[/dim]")
            raise typer.Exit(1)

        commentator = Commentator(llm)

        if pending:
            articles = (
                session.query(Article)
                .filter(Article.status == ArticleStatus.GENERATED.value)
                .filter(Article.content != None)
                .limit(10)
                .all()
            )
        elif article_id:
            articles = [session.query(Article).filter(Article.id == article_id).first()]
        else:
            console.print("[yellow]Provide article_id or use --pending[/yellow]")
            raise typer.Exit(1)

        articles = [a for a in articles if a]

        if not articles:
            console.print("[yellow]No articles for commentary[/yellow]")
            return

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating commentary...", total=len(articles))

            for article in articles:
                if filipino:
                    result = asyncio.run(commentator.generate_commentary_filipino(article))
                else:
                    result = asyncio.run(commentator.generate_commentary(article))

                commentary = Commentary(
                    article_id=article.id,
                    headline=result.get("headline"),
                    commentary_text=result.get("commentary", ""),
                    key_takeaways=", ".join(result.get("key_takeaways", []))
                    if result.get("key_takeaways")
                    else None,
                    bias_score=result.get("bias_score"),
                    fact_check_notes=result.get("bias_notes"),
                    language="fil" if filipino else "en",
                )

                existing = (
                    session.query(Commentary).filter(Commentary.article_id == article.id).first()
                )
                if existing:
                    existing.headline = commentary.headline
                    existing.commentary_text = commentary.commentary_text
                    existing.key_takeaways = commentary.key_takeaways
                    existing.bias_score = commentary.bias_score
                else:
                    session.add(commentary)

                article.status = ArticleStatus.PENDING_REVIEW.value
                session.commit()

                progress.advance(task)

        console.print(f"\n[cyan]Generated commentary for {len(articles)} articles[/cyan]")

    finally:
        session.close()


@app.command()
def social(
    article_id: Optional[int] = typer.Argument(None, help="Article ID"),
    platform: str = typer.Option(
        "twitter", "--platform", help="Platform: twitter, facebook, linkedin"
    ),
    pending: bool = typer.Option(False, "--pending", help="Generate for approved articles"),
):
    """Generate social media post."""
    session = get_session()

    try:
        llm = LLMClient()
        if not llm.check_connection():
            console.print("[red]Cannot connect to Ollama.[/red]")
            console.print(f"[yellow]Make sure Ollama is running: `ollama serve`[/yellow]")
            console.print(f"[dim]Expected at: {llm.base_url}[/dim]")
            console.print(f"[dim]Model: {llm.model}[/dim]")
            raise typer.Exit(1)

        generator = SocialPostGenerator(llm)

        if pending:
            articles = (
                session.query(Article)
                .filter(Article.status == ArticleStatus.PENDING_REVIEW.value)
                .limit(10)
                .all()
            )
        elif article_id:
            articles = [session.query(Article).filter(Article.id == article_id).first()]
        else:
            console.print("[yellow]Provide article_id or use --pending[/yellow]")
            raise typer.Exit(1)

        articles = [a for a in articles if a]

        if not articles:
            console.print("[yellow]No articles for social posts[/yellow]")
            return

        table = Table(title="Generated Social Posts")
        table.add_column("Article ID", style="cyan")
        table.add_column("Platform", style="magenta")
        table.add_column("Post", style="white", max_width=60)

        for article in articles:
            commentary = (
                session.query(Commentary).filter(Commentary.article_id == article.id).first()
            )
            comment_text = commentary.commentary_text if commentary else ""

            if platform in ["twitter", "x"]:
                post = asyncio.run(generator.generate_tweet(article, comment_text))
            elif platform == "facebook":
                post = asyncio.run(generator.generate_facebook_post(article, comment_text))
            elif platform == "linkedin":
                post = asyncio.run(generator.generate_linkedin_post(article, comment_text))
            else:
                post = asyncio.run(generator.generate_tweet(article, comment_text))

            table.add_row(
                str(article.id),
                platform,
                post[:58] + "..." if len(post) > 58 else post,
            )

            console.print(f"\n[green]Generated post for article {article.id}:[/green]")
            console.print(f"[dim]{post}[/dim]\n")

        console.print(table)

    finally:
        session.close()


@app.command()
def check():
    """Check Ollama connection and model."""
    llm = LLMClient()

    if llm.check_connection():
        console.print(f"[green]✓[/green] Connected to Ollama at {llm.base_url}")
        console.print(f"  Model: {llm.model}")
        console.print(f"  Temperature: {llm.temperature}")
    else:
        console.print("[red]✗[/red] Cannot connect to Ollama")
        console.print("[yellow]To start Ollama, run: `ollama serve`[/yellow]")
        console.print(f"  Expected at: {llm.base_url}")
        console.print(f"  Model: {llm.model}")
        console.print("\n[dim]To pull a model: `ollama pull {model}`[/dim]")
