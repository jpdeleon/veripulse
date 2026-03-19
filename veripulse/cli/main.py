"""CLI commands for Veripulse."""

import typer

from veripulse.cli import scrape, analyze, generate, review, post, status

app = typer.Typer(
    name="veripulse",
    help="Automated news aggregation, analysis, and social media dissemination",
    no_args_is_help=True,
)

app.add_typer(scrape.app, name="scrape")
app.add_typer(analyze.app, name="analyze")
app.add_typer(generate.app, name="generate")
app.add_typer(review.app, name="review")
app.add_typer(post.app, name="post")
app.add_typer(status.app, name="status")


@app.command()
def version():
    """Show version information."""
    from veripulse import __version__

    typer.echo(f"Veripulse {__version__}")


if __name__ == "__main__":
    app()
