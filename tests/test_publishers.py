"""Tests for the social media publishers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veripulse.core.publishers.social import (
    BasePublisher,
    FacebookPublisher,
    PublisherFactory,
    TwitterPublisher,
)


class TestBasePublisher:
    """Tests for BasePublisher class."""

    def test_create_base_publisher(self, mock_config):
        """Test creating base publisher."""
        with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
            publisher = BasePublisher()
        assert publisher.platform == "base"

    def test_create_post_record(self, mock_config, sample_article):
        """Test creating post record."""
        with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
            publisher = BasePublisher()
        post = publisher._create_post_record(
            article=sample_article,
            content="Test content",
            platform="twitter",
            post_url="https://twitter.com/test",
        )
        assert post.article_id == sample_article.id
        assert post.content == "Test content"
        assert post.platform == "twitter"
        assert post.post_url == "https://twitter.com/test"
        assert post.status == "posted"


class TestTwitterPublisher:
    """Tests for TwitterPublisher class."""

    @pytest.fixture
    def twitter_publisher(self, mock_config):
        """Create Twitter publisher with mocked config."""
        with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
            return TwitterPublisher()

    def test_create_twitter_publisher(self, twitter_publisher):
        """Test creating Twitter publisher."""
        assert twitter_publisher.platform == "twitter"

    def test_twitter_disabled_by_default(self, twitter_publisher):
        """Test Twitter is disabled by default."""
        assert twitter_publisher.enabled is False

    @pytest.mark.asyncio
    async def test_post_disabled_returns_error(self, twitter_publisher, sample_article):
        """Test posting when disabled returns error."""
        result = await twitter_publisher.post("Test content", sample_article)
        assert result["success"] is False
        assert "not enabled" in result["error"]

    @pytest.mark.asyncio
    async def test_post_success(self, mock_config, sample_article):
        """Test successful Twitter post."""
        mock_config.social.twitter.enabled = True
        mock_config.social.twitter.api_key = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": {"id": "123456789"}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
                publisher = TwitterPublisher()
                result = await publisher.post("Test tweet", sample_article)

        assert result["success"] is True
        assert result["post_id"] == "123456789"
        assert "twitter.com" in result["post_url"]

    @pytest.mark.asyncio
    async def test_post_failure(self, mock_config, sample_article):
        """Test failed Twitter post."""
        mock_config.social.twitter.enabled = True
        mock_config.social.twitter.api_key = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
                publisher = TwitterPublisher()
                result = await publisher.post("Test tweet", sample_article)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_schedule_returns_error(self, twitter_publisher, sample_article):
        """Test scheduling returns not implemented."""
        future = datetime(2025, 12, 25, 12, 0, 0)
        result = await twitter_publisher.schedule("Test", sample_article, future)
        assert result["success"] is False
        assert "not implemented" in result["error"]


class TestFacebookPublisher:
    """Tests for FacebookPublisher class."""

    @pytest.fixture
    def fb_publisher(self, mock_config):
        """Create Facebook publisher with mocked config."""
        with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
            return FacebookPublisher()

    def test_create_facebook_publisher(self, fb_publisher):
        """Test creating Facebook publisher."""
        assert fb_publisher.platform == "facebook"

    def test_facebook_disabled_by_default(self, fb_publisher):
        """Test Facebook is disabled by default."""
        assert fb_publisher.enabled is False

    @pytest.mark.asyncio
    async def test_post_disabled_returns_error(self, fb_publisher, sample_article):
        """Test posting when disabled returns error."""
        result = await fb_publisher.post("Test content", sample_article)
        assert result["success"] is False
        assert "not enabled" in result["error"]

    @pytest.mark.asyncio
    async def test_post_success(self, mock_config, sample_article):
        """Test successful Facebook post."""
        mock_config.social.facebook.enabled = True
        mock_config.social.facebook.page_id = "123456789"
        mock_config.social.facebook.page_access_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789_987654321"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
                publisher = FacebookPublisher()
                result = await publisher.post("Test post", sample_article)

        assert result["success"] is True
        assert result["post_id"] == "123456789_987654321"
        assert "facebook.com" in result["post_url"]

    @pytest.mark.asyncio
    async def test_post_failure(self, mock_config, sample_article):
        """Test failed Facebook post."""
        mock_config.social.facebook.enabled = True
        mock_config.social.facebook.page_id = "123456789"
        mock_config.social.facebook.page_access_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Invalid token"}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post.return_value = mock_response
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.aclose = AsyncMock()
            mock_client.return_value = mock_async_client

            with patch("veripulse.core.publishers.social.get_config", return_value=mock_config):
                publisher = FacebookPublisher()
                result = await publisher.post("Test post", sample_article)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_schedule_returns_error(self, fb_publisher, sample_article):
        """Test scheduling returns external tool suggestion."""
        future = datetime(2025, 12, 25, 12, 0, 0)
        result = await fb_publisher.schedule("Test", sample_article, future)
        assert result["success"] is False
        assert "external" in result["error"].lower()


class TestPublisherFactory:
    """Tests for PublisherFactory class."""

    def test_get_twitter_publisher(self):
        """Test getting Twitter publisher."""
        publisher = PublisherFactory.get_publisher("twitter")
        assert publisher is not None
        assert isinstance(publisher, TwitterPublisher)

    def test_get_x_publisher(self):
        """Test getting X publisher (alias for Twitter)."""
        publisher = PublisherFactory.get_publisher("x")
        assert publisher is not None
        assert isinstance(publisher, TwitterPublisher)

    def test_get_facebook_publisher(self):
        """Test getting Facebook publisher."""
        publisher = PublisherFactory.get_publisher("facebook")
        assert publisher is not None
        assert isinstance(publisher, FacebookPublisher)

    def test_get_unknown_publisher(self):
        """Test getting unknown publisher returns None."""
        publisher = PublisherFactory.get_publisher("linkedin")
        assert publisher is None

    def test_get_all_publishers(self):
        """Test getting all publishers."""
        publishers = PublisherFactory.get_all_publishers()
        assert len(publishers) == 3
        assert any(isinstance(p, TwitterPublisher) for p in publishers)
        assert any(isinstance(p, FacebookPublisher) for p in publishers)

    def test_case_insensitive(self):
        """Test publisher lookup is case insensitive."""
        twitter_lower = PublisherFactory.get_publisher("twitter")
        twitter_upper = PublisherFactory.get_publisher("TWITTER")
        twitter_mixed = PublisherFactory.get_publisher("Twitter")

        assert twitter_lower is not None
        assert twitter_upper is not None
        assert twitter_mixed is not None
