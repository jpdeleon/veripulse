"""Tests for the LLM content generators."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veripulse.core.generators.content import (
    Commentator,
    LLMClient,
    SocialPostGenerator,
    Summarizer,
)


class TestLLMClient:
    """Tests for LLMClient class."""

    def test_create_llm_client(self, mock_config):
        """Test creating LLM client."""
        with patch("veripulse.core.generators.content.get_config", return_value=mock_config):
            client = LLMClient()
            assert client.base_url == "http://localhost:11434"
            assert client.model == "llama3.2:3b"
            assert client.temperature == 0.3

    def test_create_llm_client_custom_config(self, mock_config):
        """Test creating LLM client with custom config."""
        mock_config.llm.base_url = "http://custom:11434"
        mock_config.llm.model = "gpt4"
        mock_config.llm.temperature = 0.7

        with patch("veripulse.core.generators.content.get_config", return_value=mock_config):
            client = LLMClient()
            assert client.base_url == "http://custom:11434"
            assert client.model == "gpt4"
            assert client.temperature == 0.7

    @pytest.mark.asyncio
    async def test_generate_success(self, mock_config):
        """Test successful LLM generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "This is a generated response."}}

        with patch("veripulse.core.generators.content.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_async_client.post.return_value = mock_response
                mock_async_client.__aenter__.return_value = mock_async_client
                mock_async_client.aclose = AsyncMock()
                mock_client.return_value = mock_async_client

                client = LLMClient()
                response = await client.generate("Test prompt")

        assert response == "This is a generated response."

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self, mock_config):
        """Test generation with system prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Custom response with system prompt."}
        }

        with patch("veripulse.core.generators.content.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_async_client.post.return_value = mock_response
                mock_async_client.__aenter__.return_value = mock_async_client
                mock_async_client.aclose = AsyncMock()
                mock_client.return_value = mock_async_client

                client = LLMClient()
                response = await client.generate(
                    "User prompt", system="You are a helpful assistant."
                )

        assert "Custom response" in response

    @pytest.mark.asyncio
    async def test_generate_handles_timeout(self, mock_config):
        """Test generation handles timeout."""
        import httpx

        with patch("veripulse.core.generators.content.get_config", return_value=mock_config):
            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_async_client.post.side_effect = httpx.TimeoutException("Timeout")
                mock_async_client.__aenter__.return_value = mock_async_client
                mock_async_client.aclose = AsyncMock()
                mock_client.return_value = mock_async_client

                client = LLMClient()
                response = await client.generate("Test prompt")

        assert response == ""


class TestSummarizer:
    """Tests for Summarizer class."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        return MagicMock(spec=LLMClient)

    def test_create_summarizer(self, mock_llm):
        """Test creating summarizer."""
        summarizer = Summarizer(mock_llm)
        assert summarizer.llm is mock_llm

    @pytest.mark.asyncio
    async def test_summarize_success(self, mock_llm, sample_article):
        """Test successful summarization."""
        mock_llm.generate = AsyncMock(return_value="This is a concise summary.")

        summarizer = Summarizer(mock_llm)
        summary = await summarizer.summarize(sample_article)

        assert summary == "This is a concise summary."
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_fallback_to_existing(self, mock_llm, sample_article):
        """Test summarization falls back to existing summary."""
        sample_article.summary = "Existing summary"
        sample_article.content = None

        summarizer = Summarizer(mock_llm)
        summary = await summarizer.summarize(sample_article)

        assert summary == "Existing summary"
        mock_llm.generate.assert_not_called()


class TestCommentator:
    """Tests for Commentator class."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        return MagicMock(spec=LLMClient)

    def test_create_commentator(self, mock_llm):
        """Test creating commentator."""
        commentator = Commentator(mock_llm)
        assert commentator.llm is mock_llm

    @pytest.mark.asyncio
    async def test_generate_commentary_success(self, mock_llm, sample_article):
        """Test successful commentary generation."""
        mock_llm.generate = AsyncMock(
            return_value='{"headline": "Test", "commentary": "Analysis here", "key_takeaways": ["a", "b"], "bias_notes": "none"}'
        )

        commentator = Commentator(mock_llm)
        result = await commentator.generate_commentary(sample_article)

        assert result["headline"] == "Test"
        assert result["commentary"] == "Analysis here"
        mock_llm.generate.assert_called_once()


class TestSocialPostGenerator:
    """Tests for SocialPostGenerator class."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        return MagicMock(spec=LLMClient)

    def test_create_post_generator(self, mock_llm):
        """Test creating post generator."""
        generator = SocialPostGenerator(mock_llm)
        assert generator.llm is mock_llm

    @pytest.mark.asyncio
    async def test_generate_tweet_success(self, mock_llm, sample_article):
        """Test successful tweet generation."""
        mock_llm.generate = AsyncMock(return_value="Breaking: New policy! #Philippines")

        generator = SocialPostGenerator(mock_llm)
        tweet = await generator.generate_tweet(sample_article)

        assert len(tweet) <= 280
        assert "#" in tweet

    @pytest.mark.asyncio
    async def test_generate_facebook_post_success(self, mock_llm, sample_article):
        """Test successful Facebook post generation."""
        mock_llm.generate = AsyncMock(return_value="Check out this article.")

        generator = SocialPostGenerator(mock_llm)
        post = await generator.generate_facebook_post(sample_article)

        assert len(post) <= 600
        assert "https://testnews.example.com" in post

    @pytest.mark.asyncio
    async def test_generate_linkedin_post_success(self, mock_llm, sample_article):
        """Test successful LinkedIn post generation."""
        mock_llm.generate = AsyncMock(return_value="Thought leadership article.")

        generator = SocialPostGenerator(mock_llm)
        post = await generator.generate_linkedin_post(sample_article)

        assert "https://testnews.example.com" in post

    @pytest.mark.asyncio
    async def test_generate_tweet_truncated_if_too_long(self, mock_llm, sample_article):
        """Test that long tweets are truncated."""
        long_response = "A" * 300
        mock_llm.generate = AsyncMock(return_value=long_response)

        generator = SocialPostGenerator(mock_llm)
        tweet = await generator.generate_tweet(sample_article)

        assert len(tweet) <= 280
