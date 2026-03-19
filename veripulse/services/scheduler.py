"""Scheduler service for automated scraping."""

import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from veripulse.core.config import get_config
from veripulse.core.database import init_db, Article, ArticleStatus


class Scheduler:
    def __init__(self):
        self.config = get_config()
        self.scheduler = AsyncIOScheduler()
        self._running = False

    async def scrape_job(self):
        from veripulse.cli.scrape import get_session, save_articles
        from veripulse.core.scrapers.news import ScraperFactory
        import httpx

        logger.info("Running scheduled scrape")

        _, SessionLocal = init_db(self.config.database.path)
        session = SessionLocal()

        try:
            articles_collected = 0

            rss_config = self.config.news_sources.get("rss", {})
            if rss_config.get("enabled"):
                rss_scraper = ScraperFactory.get_scraper("rss")
                if rss_scraper:
                    for feed in rss_config.get("feeds", [])[:5]:
                        try:
                            async with httpx.AsyncClient(timeout=30) as client:
                                import feedparser

                                response = await client.get(feed["url"])
                                feed_data = feedparser.parse(response.text)

                                for entry in feed_data.entries[:10]:
                                    from veripulse.core.scrapers.news import ScrapedArticle

                                    article = ScrapedArticle(
                                        title=entry.title,
                                        url=entry.link,
                                        source_name=feed_data.feed.get("title", "Unknown"),
                                        source_category=feed.get("category", "general"),
                                    )
                                    count = save_articles(session, [article])
                                    articles_collected += count
                        except Exception as e:
                            logger.error(f"Failed to scrape {feed['url']}: {e}")

            logger.info(f"Scheduled scrape completed: {articles_collected} new articles")

        finally:
            session.close()

    async def analyze_job(self):
        from veripulse.core.analyzers.nlp import (
            Categorizer,
            SentimentAnalyzer,
            ImportanceScorer,
            TrendingDetector,
        )
        from veripulse.core.database import init_db, Article, ArticleStatus

        logger.info("Running scheduled analysis")

        _, SessionLocal = init_db(self.config.database.path)
        session = SessionLocal()

        try:
            articles = (
                session.query(Article)
                .filter(Article.status == ArticleStatus.RAW.value)
                .limit(20)
                .all()
            )

            if not articles:
                return

            categorizer = Categorizer()
            sentiment_analyzer = SentimentAnalyzer()
            importance_scorer = ImportanceScorer()
            trending_detector = TrendingDetector()

            all_articles = session.query(Article).all()

            for article in articles:
                article.category = categorizer.categorize(article)
                sentiment, score = sentiment_analyzer.analyze_article(article)
                article.sentiment = sentiment
                article.sentiment_score = score
                article.importance_score = importance_scorer.calculate(article, all_articles)
                article.trending_score = trending_detector.calculate_trending_score(
                    article, all_articles
                )
                article.status = ArticleStatus.ANALYZED.value

            session.commit()
            logger.info(f"Scheduled analysis completed: {len(articles)} articles")

        finally:
            session.close()

    def start(self):
        if self._running:
            return

        interval = self.config.scraping.interval_minutes

        self.scheduler.add_job(
            self.scrape_job,
            trigger=IntervalTrigger(minutes=interval),
            id="scrape",
            name="News Scrape",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self.analyze_job,
            trigger=IntervalTrigger(minutes=interval // 2),
            id="analyze",
            name="Article Analysis",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info(f"Scheduler started (interval: {interval} minutes)")

    def stop(self):
        if self._running:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")

    def run_once(self):
        asyncio.run(self.scrape_job())
        asyncio.run(self.analyze_job())


def run_scheduler():
    scheduler = Scheduler()
    scheduler.start()

    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    run_scheduler()
