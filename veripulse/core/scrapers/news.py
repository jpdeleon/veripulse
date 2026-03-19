"""News scrapers for Veripulse."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx
import feedparser
from newspaper import Article as NewsArticle
from newspaper import Config as NewspaperConfig
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from veripulse.core.config import get_config


@dataclass
class ScrapedArticle:
    title: str
    url: str
    content: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None
    source_name: str = ""
    source_category: str = "general"


class BaseScraper(ABC):
    @abstractmethod
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        pass


class RSSScraper(BaseScraper):
    def __init__(self):
        self.config = get_config()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        articles = []
        url = kwargs.get("url")
        category = kwargs.get("category", "general")

        if not url:
            return articles

        try:
            async with httpx.AsyncClient(timeout=self.config.scraping.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()

            feed = feedparser.parse(response.text)
            source_name = feed.feed.get("title", "Unknown")

            for entry in feed.entries[: self.config.scraping.max_articles_per_run]:
                try:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    article = ScrapedArticle(
                        title=entry.title,
                        url=entry.link,
                        source_name=source_name,
                        source_category=category,
                        published_at=published,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")

        return articles


class NewsAPIScraper(BaseScraper):
    def __init__(self):
        self.config = get_config()
        self.api_config = self.config.news_sources.get("newsapi", {})
        self.api_key = self.api_config.get("api_key", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        articles = []
        topic = kwargs.get("topic", "")

        if not self.api_key:
            logger.warning("NewsAPI key not configured")
            return articles

        try:
            async with httpx.AsyncClient(timeout=self.config.scraping.timeout_seconds) as client:
                params = {
                    "apiKey": self.api_key,
                    "q": topic,
                    "language": "en",
                    "pageSize": self.config.scraping.max_articles_per_run,
                }
                response = await client.get("https://newsapi.org/v2/everything", params=params)
                response.raise_for_status()
                data = response.json()

            for item in data.get("articles", []):
                try:
                    published = None
                    if item.get("publishedAt"):
                        published = datetime.fromisoformat(
                            item["publishedAt"].replace("Z", "+00:00")
                        )

                    article = ScrapedArticle(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        summary=item.get("description", ""),
                        author=item.get("author"),
                        published_at=published,
                        image_url=item.get("urlToImage"),
                        source_name=item.get("source", {}).get("name", "Unknown"),
                        source_category=topic,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse NewsAPI article: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch from NewsAPI: {e}")

        return articles


class NewsDataScraper(BaseScraper):
    def __init__(self):
        self.config = get_config()
        self.api_config = self.config.news_sources.get("newsdata", {})
        self.api_key = self.api_config.get("api_key", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        articles = []
        topic = kwargs.get("topic", "")

        if not self.api_key:
            logger.warning("NewsData API key not configured")
            return articles

        try:
            async with httpx.AsyncClient(timeout=self.config.scraping.timeout_seconds) as client:
                params = {
                    "apikey": self.api_key,
                    "q": topic,
                    "language": "en",
                }
                response = await client.get("https://newsdata.io/api/1/latest", params=params)
                response.raise_for_status()
                data = response.json()

            for item in data.get("results", []):
                try:
                    published = None
                    if item.get("pubDate"):
                        published = datetime.fromisoformat(item["pubDate"].replace("Z", "+00:00"))

                    article = ScrapedArticle(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        content=item.get("content", ""),
                        summary=item.get("description", ""),
                        author=item.get("creator", [None])[0] if item.get("creator") else None,
                        published_at=published,
                        image_url=item.get("image_url"),
                        source_name=item.get("source_id", "Unknown"),
                        source_category=topic,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse NewsData article: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch from NewsData: {e}")

        return articles


class NewspaperScraper:
    def __init__(self):
        self.config = get_config()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        news_config = NewspaperConfig()
        news_config.request_timeout = self.config.scraping.timeout_seconds

        try:
            article = NewsArticle(url, config=news_config)
            article.download()
            article.parse()
            article.nlp()

            return ScrapedArticle(
                title=article.title,
                url=url,
                content=article.text,
                summary=article.summary,
                author=", ".join(article.authors) if article.authors else None,
                published_at=article.publish_date,
                image_url=article.top_image,
            )
        except Exception as e:
            logger.error(f"Failed to scrape article {url}: {e}")
            return None


class ScraperFactory:
    _scrapers = {
        "rss": RSSScraper,
        "newsapi": NewsAPIScraper,
        "newsdata": NewsDataScraper,
    }

    @classmethod
    def get_scraper(cls, scraper_type: str) -> Optional[BaseScraper]:
        scraper_class = cls._scrapers.get(scraper_type)
        if scraper_class:
            return scraper_class()
        return None
