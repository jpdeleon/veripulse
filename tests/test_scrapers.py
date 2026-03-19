"""Tests for the news scrapers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veripulse.core.scrapers.news import (
    BaseScraper,
    NewsAPIScraper,
    NewsDataScraper,
    RSSScraper,
    ScrapedArticle,
    ScraperFactory,
)


class TestScrapedArticle:
    """Tests for the ScrapedArticle dataclass."""

    def test_create_minimal(self):
        """Test creating article with minimal fields."""
        article = ScrapedArticle(title="Test", url="https://test.com")
        assert article.title == "Test"
        assert article.url == "https://test.com"
        assert article.content is None
        assert article.source_name == ""

    def test_create_full(self):
        """Test creating article with all fields."""
        published = datetime(2025, 1, 15, 12, 0, 0)
        article = ScrapedArticle(
            title="Full Article",
            url="https://test.com/article",
            content="Article content here",
            summary="Brief summary",
            author="John Doe",
            published_at=published,
            image_url="https://test.com/image.jpg",
            source_name="Test News",
            source_category="politics",
        )
        assert article.title == "Full Article"
        assert article.published_at == published
        assert article.source_category == "politics"


class TestRSSScraper:
    """Tests for the RSSScraper class."""

    @pytest.fixture
    def rss_scraper(self, mock_config):
        """Create RSS scraper with mocked config."""
        with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
            return RSSScraper()

    @pytest.mark.asyncio
    async def test_fetch_articles_success(self, rss_scraper, mock_config):
        """Test successful RSS fetching."""
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Article 1</title>
                    <link>https://test.com/1</link>
                </item>
                <item>
                    <title>Article 2</title>
                    <link>https://test.com/2</link>
                </item>
            </channel>
        </rss>"""
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
                scraper = RSSScraper()
                articles = await scraper.fetch_articles(url="https://test.com/feed")

        assert len(articles) == 2
        assert articles[0].title == "Article 1"
        assert articles[0].source_name == "Test Feed"

    @pytest.mark.asyncio
    async def test_fetch_articles_no_url(self, rss_scraper):
        """Test fetch returns empty when no URL provided."""
        articles = await rss_scraper.fetch_articles()
        assert articles == []

    @pytest.mark.asyncio
    async def test_fetch_articles_handles_exception(self, mock_config):
        """Test fetch handles exceptions gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.side_effect = Exception("Network error")
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
                scraper = RSSScraper()
                articles = await scraper.fetch_articles(url="https://test.com/feed")

        assert articles == []


class TestNewsAPIScraper:
    """Tests for the NewsAPIScraper class."""

    @pytest.fixture
    def newsapi_scraper(self, mock_config):
        """Create NewsAPI scraper with mocked config."""
        with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
            return NewsAPIScraper()

    @pytest.mark.asyncio
    async def test_fetch_articles_success(self, mock_config):
        """Test successful NewsAPI fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "API Article 1",
                    "url": "https://test.com/1",
                    "content": "Content here",
                    "description": "Brief",
                    "publishedAt": "2025-01-15T12:00:00Z",
                    "source": {"name": "Test Source"},
                    "urlToImage": "https://test.com/img.jpg",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
                scraper = NewsAPIScraper()
                articles = await scraper.fetch_articles(topic="philippines")

        assert len(articles) == 1
        assert articles[0].title == "API Article 1"
        assert articles[0].source_name == "Test Source"

    @pytest.mark.asyncio
    async def test_fetch_articles_no_api_key(self, mock_config):
        """Test fetch returns empty when no API key."""
        mock_config.news_sources = {"newsapi": {"api_key": ""}}
        with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
            scraper = NewsAPIScraper()
            articles = await scraper.fetch_articles(topic="philippines")
        assert articles == []


class TestNewsDataScraper:
    """Tests for the NewsDataScraper class."""

    @pytest.fixture
    def newsdata_scraper(self, mock_config):
        """Create NewsData scraper with mocked config."""
        with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
            return NewsDataScraper()

    @pytest.mark.asyncio
    async def test_fetch_articles_success(self, mock_config):
        """Test successful NewsData fetching."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "NewsData Article",
                    "link": "https://test.com/article",
                    "content": "Full content",
                    "description": "Summary",
                    "pubDate": "2025-01-15T12:00:00Z",
                    "source_id": "TestSource",
                    "creator": ["Author Name"],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
                scraper = NewsDataScraper()
                articles = await scraper.fetch_articles(topic="news")

        assert len(articles) == 1
        assert articles[0].title == "NewsData Article"
        assert articles[0].author == "Author Name"

    @pytest.mark.asyncio
    async def test_fetch_articles_no_api_key(self, mock_config):
        """Test fetch returns empty when no API key."""
        mock_config.news_sources = {"newsdata": {"api_key": ""}}
        with patch("veripulse.core.scrapers.news.get_config", return_value=mock_config):
            scraper = NewsDataScraper()
            articles = await scraper.fetch_articles(topic="news")
        assert articles == []


class TestScraperFactory:
    """Tests for the ScraperFactory class."""

    def test_get_rss_scraper(self):
        """Test getting RSS scraper."""
        scraper = ScraperFactory.get_scraper("rss")
        assert scraper is not None
        assert isinstance(scraper, RSSScraper)

    def test_get_newsapi_scraper(self):
        """Test getting NewsAPI scraper."""
        scraper = ScraperFactory.get_scraper("newsapi")
        assert scraper is not None
        assert isinstance(scraper, NewsAPIScraper)

    def test_get_newsdata_scraper(self):
        """Test getting NewsData scraper."""
        scraper = ScraperFactory.get_scraper("newsdata")
        assert scraper is not None
        assert isinstance(scraper, NewsDataScraper)

    def test_get_unknown_scraper(self):
        """Test getting unknown scraper returns None."""
        scraper = ScraperFactory.get_scraper("unknown")
        assert scraper is None

    def test_all_scrapers_registered(self):
        """Test all scraper types are registered."""
        expected = ["rss", "newsapi", "newsdata"]
        for scraper_type in expected:
            scraper = ScraperFactory.get_scraper(scraper_type)
            assert scraper is not None


class TestBaseScraper:
    """Tests for BaseScraper abstract class."""

    def test_base_scraper_is_abstract(self):
        """Test BaseScraper cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseScraper()
