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


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Cache-Control": "max-age=0",
}


def _is_js_challenge(resp: httpx.Response) -> bool:
    """Detect Cloudflare or similar JS challenges."""
    if resp.status_code in (403, 429, 503):
        mitigated = resp.headers.get("cf-mitigated", "")
        server = resp.headers.get("server", "")
        if mitigated or "cloudflare" in server.lower():
            return True
        body = resp.text[:500].lower()
        if "enable javascript" in body or "just a moment" in body:
            return True
    return False


_CHALLENGE_TITLES = {"just a moment", "attention required", "access denied", "security check"}


def _is_challenge_page(html: str) -> bool:
    """Return True if Playwright captured a JS challenge page instead of real content."""
    lower = html[:2000].lower()
    return any(t in lower for t in _CHALLENGE_TITLES)


async def _fetch_html_playwright(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch page HTML using a headless Chromium browser (bypasses JS challenges).

    Returns None if the challenge page could not be bypassed.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=BROWSER_HEADERS["User-Agent"],
            locale="en-US",
        )
        page = await ctx.new_page()
        await page.goto(url, wait_until="load", timeout=timeout * 1000)
        # wait up to 8s for challenge to resolve
        for _ in range(4):
            await page.wait_for_timeout(2000)
            html = await page.content()
            if not _is_challenge_page(html):
                await browser.close()
                return html
        await browser.close()
        logger.warning(f"Cloudflare challenge not bypassed for {url}")
        return None


class NewspaperScraper:
    def __init__(self):
        self.config = get_config()

    def _parse_html(self, url: str, html: str) -> ScrapedArticle:
        news_config = NewspaperConfig()
        news_config.request_timeout = self.config.scraping.timeout_seconds
        article = NewsArticle(url, config=news_config)
        article.set_html(html)
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def scrape_article(self, url: str) -> Optional[ScrapedArticle]:
        try:
            async with httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                follow_redirects=True,
                timeout=self.config.scraping.timeout_seconds,
            ) as client:
                resp = await client.get(url)

            if _is_js_challenge(resp):
                logger.info(f"JS challenge detected for {url}, retrying with Playwright")
                html = await _fetch_html_playwright(url, self.config.scraping.timeout_seconds)
                if html is None:
                    logger.warning(f"Cloudflare challenge not bypassed for {url}")
                    return None
            else:
                resp.raise_for_status()
                html = resp.text

            return self._parse_html(url, html)

        except Exception as e:
            logger.error(f"Failed to scrape article {url}: {e}")
            return None


class DuckDuckGoNewsScraper(BaseScraper):
    """Scrapes news via DuckDuckGo News search. Free, no API key, returns direct article URLs."""

    def __init__(self):
        self.config = get_config()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        from ddgs import DDGS

        topic = kwargs.get("topic", "")
        max_results = kwargs.get("max_results", self.config.scraping.max_articles_per_run)
        articles = []

        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(topic, max_results=max_results))

            for item in results:
                try:
                    published = None
                    if item.get("date"):
                        from dateutil import parser as dateparser
                        published = dateparser.parse(item["date"])

                    article = ScrapedArticle(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        summary=item.get("body", ""),
                        image_url=item.get("image"),
                        published_at=published,
                        source_name=item.get("source", "DuckDuckGo News"),
                        source_category=topic,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse DDG news item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch DDG news for '{topic}': {e}")

        return articles

    async def fetch_all_topics(self) -> list[ScrapedArticle]:
        """Fetch articles for all topics defined in config, deduplicating by URL."""
        topics = self.config.topics if hasattr(self.config, "topics") else []
        all_articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        for topic in topics:
            articles = await self.fetch_articles(topic=topic)
            for article in articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)

        return all_articles


class GoogleNewsRSSScraper(BaseScraper):
    """Scrapes Google News RSS feeds for configured topics. No API key required."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self):
        self.config = get_config()

    def _build_url(self, topic: str) -> str:
        import urllib.parse
        params = urllib.parse.urlencode({"q": topic, "hl": "en", "gl": "PH", "ceid": "PH:en"})
        return f"{self.BASE_URL}?{params}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_articles(self, **kwargs) -> list[ScrapedArticle]:
        topic = kwargs.get("topic", "")
        url = self._build_url(topic)
        articles = []

        try:
            async with httpx.AsyncClient(timeout=self.config.scraping.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()

            feed = feedparser.parse(response.text)

            for entry in feed.entries[: self.config.scraping.max_articles_per_run]:
                try:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    source_name = "Google News"
                    if hasattr(entry, "source") and isinstance(entry.source, dict):
                        source_name = entry.source.get("title", "Google News")

                    article = ScrapedArticle(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        summary=entry.get("summary", ""),
                        published_at=published,
                        source_name=source_name,
                        source_category=topic,
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse Google News entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to fetch Google News RSS for '{topic}': {e}")

        return articles

    async def fetch_all_topics(self) -> list[ScrapedArticle]:
        """Fetch articles for all topics defined in config, deduplicating by URL."""
        topics = self.config.topics if hasattr(self.config, "topics") else []
        all_articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        for topic in topics:
            articles = await self.fetch_articles(topic=topic)
            for article in articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)

        return all_articles


class ScraperFactory:
    _scrapers = {
        "rss": RSSScraper,
        "newsapi": NewsAPIScraper,
        "newsdata": NewsDataScraper,
        "google_news": GoogleNewsRSSScraper,
        "ddg_news": DuckDuckGoNewsScraper,
    }

    @classmethod
    def get_scraper(cls, scraper_type: str) -> Optional[BaseScraper]:
        scraper_class = cls._scrapers.get(scraper_type)
        if scraper_class:
            return scraper_class()
        return None
