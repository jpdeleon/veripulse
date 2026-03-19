"""Tests for the database models."""

from datetime import datetime

import pytest

from veripulse.core.database import (
    Article,
    ArticleStatus,
    Commentary,
    Sentiment,
    SocialPost,
    Source,
    Topic,
)


class TestSource:
    """Tests for the Source model."""

    def test_create_source(self, db_session):
        """Test creating a source."""
        source = Source(
            name="Philippine Daily Inquirer",
            url="https://newsinfo.inquirer.net",
            category="news",
            credibility_score=0.9,
        )
        db_session.add(source)
        db_session.commit()

        assert source.id is not None
        assert source.name == "Philippine Daily Inquirer"
        assert source.is_active is True
        assert source.created_at is not None

    def test_source_unique_name(self, db_session, sample_source):
        """Test that source names must be unique."""
        duplicate = Source(
            name=sample_source.name,
            url="https://different.example.com",
            category="news",
        )
        db_session.add(duplicate)
        with pytest.raises(Exception):
            db_session.commit()

    def test_source_articles_relationship(self, db_session, sample_source, sample_article):
        """Test source-articles relationship."""
        assert len(sample_source.articles) == 1
        assert sample_source.articles[0].title == sample_article.title


class TestArticle:
    """Tests for the Article model."""

    def test_create_article(self, db_session, sample_source):
        """Test creating an article."""
        article = Article(
            source_id=sample_source.id,
            title="Breaking: New Senate Bill Filed",
            url="https://test.com/article",
            content="The senator filed a new bill today.",
            status=ArticleStatus.RAW.value,
        )
        db_session.add(article)
        db_session.commit()

        assert article.id is not None
        assert article.status == "raw"
        assert article.importance_score == 0.5
        assert article.trending_score == 0.0

    def test_article_status_transitions(self, db_session, sample_article):
        """Test article status can be updated."""
        assert sample_article.status == "raw"

        sample_article.status = ArticleStatus.ANALYZED.value
        db_session.commit()
        assert sample_article.status == "analyzed"

        sample_article.status = ArticleStatus.PENDING_REVIEW.value
        db_session.commit()
        assert sample_article.status == "pending_review"

    def test_article_with_sentiment(self, db_session, sample_article):
        """Test article sentiment attributes."""
        sample_article.sentiment = Sentiment.POSITIVE.value
        sample_article.sentiment_score = 0.75
        db_session.commit()

        assert sample_article.sentiment == "positive"
        assert sample_article.sentiment_score == 0.75

    def test_article_importance_score_bounds(self, db_session, sample_source):
        """Test that importance score defaults within bounds."""
        article = Article(
            source_id=sample_source.id,
            title="Test",
            url="https://test.com/t",
            importance_score=0.8,
        )
        db_session.add(article)
        db_session.commit()

        assert 0.0 <= article.importance_score <= 1.0

    def test_article_commentary_relationship(self, db_session, sample_article, sample_commentary):
        """Test article-commentary relationship."""
        assert sample_article.commentary is not None
        assert sample_article.commentary.headline == sample_commentary.headline

    def test_article_social_posts_relationship(
        self, db_session, sample_article, sample_social_post
    ):
        """Test article-social_posts relationship."""
        assert len(sample_article.social_posts) == 1
        assert sample_article.social_posts[0].platform == "twitter"


class TestCommentary:
    """Tests for the Commentary model."""

    def test_create_commentary(self, db_session, sample_article):
        """Test creating commentary."""
        commentary = Commentary(
            article_id=sample_article.id,
            headline="Analysis: Key Takeaways",
            commentary_text="This article reveals important developments.",
            key_takeaways="Point 1, Point 2, Point 3",
            language="en",
        )
        db_session.add(commentary)
        db_session.commit()

        assert commentary.id is not None
        assert commentary.bias_score is None
        assert commentary.fact_check_notes is None

    def test_commentary_bilingual(self, db_session, sample_article):
        """Test bilingual commentary."""
        commentary = Commentary(
            article_id=sample_article.id,
            headline="Mga Mahahalagang Punkt",
            commentary_text="Ang article na ito ay nagpapakita ng mahalagang developments.",
            language="filipino",
        )
        db_session.add(commentary)
        db_session.commit()

        assert commentary.language == "filipino"


class TestSocialPost:
    """Tests for the SocialPost model."""

    def test_create_social_post(self, db_session, sample_article):
        """Test creating a social post."""
        post = SocialPost(
            article_id=sample_article.id,
            platform="facebook",
            content="Check out this article!",
            hashtags="#News #Philippines",
        )
        db_session.add(post)
        db_session.commit()

        assert post.id is not None
        assert post.status == "pending"
        assert post.scheduled_at is None
        assert post.posted_at is None

    def test_social_post_scheduled(self, db_session, sample_article):
        """Test scheduled post."""
        future_time = datetime(2025, 12, 25, 12, 0, 0)
        post = SocialPost(
            article_id=sample_article.id,
            platform="twitter",
            content="Holiday news update",
            status="scheduled",
            scheduled_at=future_time,
        )
        db_session.add(post)
        db_session.commit()

        assert post.status == "scheduled"
        assert post.scheduled_at == future_time

    def test_social_post_posted(self, db_session, sample_article):
        """Test posted status with URL."""
        post = SocialPost(
            article_id=sample_article.id,
            platform="twitter",
            content="Breaking news!",
            status="posted",
            posted_at=datetime.utcnow(),
            post_url="https://twitter.com/user/status/123",
            engagement=150,
        )
        db_session.add(post)
        db_session.commit()

        assert post.status == "posted"
        assert post.post_url is not None
        assert post.engagement == 150


class TestTopic:
    """Tests for the Topic model."""

    def test_create_topic(self, db_session):
        """Test creating a topic."""
        topic = Topic(
            name="Marcos Administration",
            keywords="Marcos,BBM,President,Government",
        )
        db_session.add(topic)
        db_session.commit()

        assert topic.id is not None
        assert topic.is_active is True

    def test_topic_unique_name(self, db_session):
        """Test topic names must be unique."""
        topic1 = Topic(name="Climate Change", keywords="climate,environment")
        db_session.add(topic1)
        db_session.commit()

        topic2 = Topic(name="Climate Change", keywords="global warming")
        db_session.add(topic2)
        with pytest.raises(Exception):
            db_session.commit()


class TestArticleStatus:
    """Tests for ArticleStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected statuses exist."""
        assert ArticleStatus.RAW.value == "raw"
        assert ArticleStatus.ANALYZED.value == "analyzed"
        assert ArticleStatus.GENERATED.value == "generated"
        assert ArticleStatus.PENDING_REVIEW.value == "pending_review"
        assert ArticleStatus.APPROVED.value == "approved"
        assert ArticleStatus.REJECTED.value == "rejected"
        assert ArticleStatus.SCHEDULED.value == "scheduled"
        assert ArticleStatus.POSTED.value == "posted"
        assert ArticleStatus.FAILED.value == "failed"


class TestSentiment:
    """Tests for Sentiment enum."""

    def test_all_sentiments_defined(self):
        """Test all expected sentiments exist."""
        assert Sentiment.POSITIVE.value == "positive"
        assert Sentiment.NEGATIVE.value == "negative"
        assert Sentiment.NEUTRAL.value == "neutral"
        assert Sentiment.MIXED.value == "mixed"
