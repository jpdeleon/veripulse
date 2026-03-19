# Veripulse

Automated news aggregation, analysis, generation, and social media dissemination for Philippine news.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Multi-Source Scraping**: NewsData.io API, NewsAPI, RSS feeds
- **Intelligent Categorization**: Keyword and NLP-based article classification
- **Sentiment Analysis**: Positive/negative/neutral detection
- **Importance Ranking**: Prioritize articles by relevance
- **LLM-Powered Generation**: Summaries and commentary using Ollama
- **Human Review Workflow**: Full approval process before posting
- **Social Media Integration**: X (Twitter), Facebook scheduling

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) for local LLM inference
- SQLite (included)

## Installation

```bash
git clone https://github.com/veripulse/veripulse.git
cd veripulse
pip install -e .
```

Or with uv:

```bash
git clone https://github.com/veripulse/veripulse.git
cd veripulse
uv pip install -e .
```

## Setup

### 1. Configure API Keys

Create a `.env` file in the project root:

```bash
# News APIs
NEWSDATA_API_KEY="your-newsdata-api-key"
NEWSAPI_API_KEY="your-newsapi-key"

# LLM (optional - defaults shown)
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="llama3.2:3b"

# Social Media (optional)
TWITTER_API_KEY=""
TWITTER_API_SECRET=""
TWITTER_ACCESS_TOKEN=""
TWITTER_ACCESS_SECRET=""
FACEBOOK_PAGE_ACCESS_TOKEN=""
FACEBOOK_PAGE_ID=""
```

Get your API keys:
- [NewsData.io](https://newsdata.io/) - Free tier available
- [NewsAPI.org](https://newsapi.org/) - Free tier available

### 2. Start Ollama

```bash
# Pull a model (choose one that fits your system)
ollama pull llama3.2:3b     # 2GB - recommended
ollama pull llama3.2:1b     # 1.3GB - lighter
ollama pull gemma3:latest   # varies

# Start Ollama (keep running in background)
ollama serve
```

### 3. Verify Setup

```bash
veripulse generate check
```

Expected output:
```
✓ Connected to Ollama at http://localhost:11434
  Model: llama3.2:3b
  Temperature: 0.3
```

## Quick Start

```bash
# 1. Scrape news
veripulse scrape all --limit 10

# 2. Analyze articles (categorize, sentiment)
veripulse analyze all

# 3. Generate summaries
veripulse generate summary --pending

# 4. Generate commentary
veripulse generate commentary --pending

# 5. Review and approve
veripulse review list
veripulse review show 1
veripulse review approve 1

# 6. Schedule social posts
veripulse post schedule 1 twitter
veripulse post schedule 1 facebook

# 7. Check status
veripulse status main
veripulse status queue
```

## Workflow

```
┌─────────┐    ┌─────────┐    ┌───────────┐    ┌───────┐    ┌────────┐
│ Scrape  │ -> │ Analyze │ -> │ Generate  │ -> │ Review│ -> │  Post  │
└─────────┘    └─────────┘    └───────────┘    └───────┘    └────────┘
    │              │               │              │              │
    ▼              ▼               ▼              ▼              ▼
   raw         analyzed        commentary      approved       scheduled
                                summaries                        │
                                                            ┌────┴────┐
                                                            ▼         ▼
                                                         twitter   facebook
```

## Commands Reference

### Scrape
```bash
veripulse scrape all              # Scrape from all enabled sources
veripulse scrape all --limit 20  # Limit articles per source
veripulse scrape rss <url>       # Scrape specific RSS feed
veripulse scrape article <url>    # Scrape full article content
veripulse scrape sources          # List configured sources
```

### Analyze
```bash
veripulse analyze all             # Analyze all raw articles
veripulse analyze <id>           # Analyze specific article
```

### Generate
```bash
veripulse generate summary --pending        # Generate English summaries
veripulse generate summary --pending --bilingual  # Filipino summaries
veripulse generate commentary --pending     # Generate commentary
veripulse generate commentary --pending --filipino  # Filipino commentary
veripulse generate social 1 twitter        # Generate tweet for article
veripulse generate check                    # Check Ollama connection
```

### Review
```bash
veripulse review list              # List articles needing review
veripulse review show <id>         # Show article details
veripulse review approve <id>       # Approve for posting
veripulse review reject <id>       # Reject article
```

### Post
```bash
veripulse post schedule <id> <platform>     # Schedule a post
veripulse post now <id> <platform>          # Post immediately
veripulse post pending                       # List scheduled posts
veripulse post cancel <post_id>             # Cancel scheduled post
veripulse post bulk twitter --limit 10       # Create posts for approved articles
```

### Status
```bash
veripulse status main        # Overall system status
veripulse status articles    # List recent articles
veripulse status queue       # Work queue summary
veripulse status top         # Top articles by importance
```

## Project Structure

```
veripulse/
├── cli/                    # CLI commands (Typer)
│   ├── main.py            # Main app entry
│   ├── scrape.py          # Scraping commands
│   ├── analyze.py         # Analysis commands
│   ├── generate.py        # Generation commands
│   ├── review.py          # Review workflow
│   ├── post.py            # Social posting
│   └── status.py          # Status/monitoring
├── core/                   # Core modules
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLAlchemy models
│   ├── scrapers/         # News source scrapers
│   │   └── news.py       # RSS, NewsAPI, NewsData
│   ├── analyzers/        # NLP processing
│   │   └── nlp.py        # Categorization, sentiment
│   ├── generators/       # LLM content generation
│   │   └── content.py    # Summaries, commentary
│   └── publishers/       # Social media APIs
│       └── social.py      # Twitter, Facebook
├── services/             # Background services
│   └── scheduler.py      # Scheduled tasks
├── config.yaml           # Default configuration
├── .env                  # API keys (not committed)
└── data/                 # SQLite database
```

## Configuration

Edit `veripulse/config.yaml` to customize:

```yaml
scraping:
  interval_minutes: 60
  max_articles_per_run: 50
  timeout_seconds: 30

llm:
  provider: ollama
  base_url: http://localhost:11434
  model: llama3.2:3b
  temperature: 0.3
  max_tokens: 2048

editorial:
  auto_generate_summary: false
  require_full_review: true
  max_article_age_hours: 24
```

## Environment Variables

All sensitive credentials should be set via environment variables (in `.env` file):

| Variable | Description |
|----------|-------------|
| `NEWSDATA_API_KEY` | NewsData.io API key |
| `NEWSAPI_API_KEY` | NewsAPI.org API key |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_MODEL` | Ollama model name |
| `TWITTER_*` | Twitter API credentials |
| `FACEBOOK_*` | Facebook API credentials |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check .

# Run type checking
mypy veripulse/

# Run tests
pytest
```

## License

MIT License - see LICENSE file for details.
