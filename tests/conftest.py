"""Pytest fixtures for Veripulse tests."""

import os
import tempfile
from collections.abc import Generator
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from veripulse.core.database import (
    Article,
    Base,
    Commentary,
    SocialPost,
    Source,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_source(db_session: Session) -> Source:
    """Create a sample news source."""
    source = Source(
        name="Test News",
        url="https://testnews.example.com",
        category="news",
        credibility_score=0.8,
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()
    return source


@pytest.fixture
def sample_article(db_session: Session, sample_source: Source) -> Article:
    """Create a sample article."""
    article = Article(
        source_id=sample_source.id,
        title="Marcos administration announces new economic policies",
        url="https://testnews.example.com/article/123",
        content="The Marcos administration announced new economic policies aimed at boosting GDP growth and controlling inflation.",
        author="John Doe",
        published_at=datetime.utcnow(),
        status="raw",
        category="economy",
    )
    db_session.add(article)
    db_session.commit()
    return article


@pytest.fixture
def sample_articles(db_session: Session, sample_source: Source) -> list[Article]:
    """Create multiple sample articles."""
    articles_data = [
        {
            "title": "Senate passes new cybersecurity bill",
            "url": "https://testnews.example.com/article/1",
            "content": "The Senate has passed a new cybersecurity bill that will impact tech companies.",
            "category": "politics",
            "sentiment": "neutral",
        },
        {
            "title": "PBA Finals: Team A wins championship",
            "url": "https://testnews.example.com/article/2",
            "content": "Team A won the PBA Finals in an exciting Game 7 match against Team B.",
            "category": "sports",
            "sentiment": "positive",
        },
        {
            "title": "Typhoon Odette causes widespread damage in Visayas",
            "url": "https://testnews.example.com/article/3",
            "content": "Typhoon Odette has caused widespread damage across the Visayas region.",
            "category": "disaster",
            "sentiment": "negative",
        },
        {
            "title": "New hospital opens in Manila",
            "url": "https://testnews.example.com/article/4",
            "content": "A new state-of-the-art hospital opened today in Manila.",
            "category": "health",
            "sentiment": "positive",
        },
        {
            "title": "Police arrest suspects in robbery case",
            "url": "https://testnews.example.com/article/5",
            "content": "The PNP has arrested several suspects in connection with a series of robberies.",
            "category": "crime",
            "sentiment": "neutral",
        },
    ]

    articles = []
    for data in articles_data:
        article = Article(
            source_id=sample_source.id,
            **data,
            status="analyzed",
            importance_score=0.5,
        )
        db_session.add(article)
        articles.append(article)

    db_session.commit()
    return articles


@pytest.fixture
def sample_commentary(db_session: Session, sample_article: Article) -> Commentary:
    """Create sample commentary for an article."""
    commentary = Commentary(
        article_id=sample_article.id,
        headline="Key developments in economic policy",
        commentary_text="This represents a significant shift in economic approach.",
        key_takeaways="1. Focus on growth\n2. Inflation control priority",
        language="en",
        bias_score=0.2,
    )
    db_session.add(commentary)
    db_session.commit()
    return commentary


@pytest.fixture
def sample_social_post(db_session: Session, sample_article: Article) -> SocialPost:
    """Create a sample social post."""
    post = SocialPost(
        article_id=sample_article.id,
        platform="twitter",
        content="New economic policies announced by the Marcos administration.",
        status="pending",
        hashtags="#Philippines #Economy #Marcos",
    )
    db_session.add(post)
    db_session.commit()
    return post


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Provide a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    from unittest.mock import patch

    mock_cfg = MagicMock()
    mock_cfg.scraping.timeout_seconds = 30
    mock_cfg.scraping.max_articles_per_run = 50
    mock_cfg.news_sources = {
        "newsdata": {"api_key": "test-key"},
        "newsapi": {"api_key": "test-key"},
    }
    mock_cfg.llm.base_url = "http://localhost:11434"
    mock_cfg.llm.model = "llama3.2:3b"
    mock_cfg.llm.temperature = 0.3
    mock_cfg.social.twitter.enabled = False
    mock_cfg.social.twitter.api_key = ""
    mock_cfg.social.facebook.enabled = False
    mock_cfg.social.facebook.page_id = ""
    mock_cfg.social.facebook.page_access_token = ""

    with patch("veripulse.core.config.get_config", return_value=mock_cfg):
        yield mock_cfg
