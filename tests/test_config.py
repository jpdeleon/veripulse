"""Tests for the configuration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from veripulse.core.config import (
    Config,
    DatabaseConfig,
    EditorialConfig,
    FacebookConfig,
    LLMConfig,
    LoggingConfig,
    ScrapingConfig,
    SocialConfig,
    TwitterConfig,
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_defaults(self):
        """Test default values."""
        config = DatabaseConfig()
        assert config.path == "data/veripulse.db"
        assert config.echo is False

    def test_custom_values(self):
        """Test custom values."""
        config = DatabaseConfig(path="/custom/path.db", echo=True)
        assert config.path == "/custom/path.db"
        assert config.echo is True


class TestScrapingConfig:
    """Tests for ScrapingConfig."""

    def test_defaults(self):
        """Test default values."""
        config = ScrapingConfig()
        assert config.interval_minutes == 60
        assert config.max_articles_per_run == 50
        assert config.timeout_seconds == 30
        assert config.retry_attempts == 3


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_defaults(self):
        """Test default values."""
        config = LLMConfig()
        assert config.provider == "ollama"
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama3.2:3b"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 120


class TestEditorialConfig:
    """Tests for EditorialConfig."""

    def test_defaults(self):
        """Test default values."""
        config = EditorialConfig()
        assert config.auto_generate_summary is False
        assert config.require_full_review is True
        assert config.max_article_age_hours == 24


class TestSocialConfig:
    """Tests for SocialConfig."""

    def test_defaults(self):
        """Test default values."""
        config = SocialConfig()
        assert config.twitter.enabled is False
        assert config.facebook.enabled is False

    def test_twitter_config(self):
        """Test Twitter config."""
        config = SocialConfig(
            twitter=TwitterConfig(
                enabled=True,
                api_key="test-key",
                api_secret="test-secret",
            )
        )
        assert config.twitter.enabled is True
        assert config.twitter.api_key == "test-key"

    def test_facebook_config(self):
        """Test Facebook config."""
        config = SocialConfig(
            facebook=FacebookConfig(
                enabled=True,
                page_access_token="test-token",
                page_id="12345",
            )
        )
        assert config.facebook.enabled is True
        assert config.facebook.page_id == "12345"


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_defaults(self):
        """Test default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == "data/veripulse.log"
        assert config.rotation == "100 MB"
        assert config.retention == "30 days"


class TestConfigLoad:
    """Tests for Config loading from YAML."""

    def test_load_from_file(self):
        """Test loading config from YAML file."""
        config_data = {
            "scraping": {
                "interval_minutes": 30,
                "max_articles_per_run": 100,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = Config.load(Path(temp_path))
            assert config.scraping.interval_minutes == 30
            assert config.scraping.max_articles_per_run == 100
        finally:
            os.unlink(temp_path)

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file returns defaults."""
        config = Config.load(Path("/nonexistent/config.yaml"))
        assert config.scraping.interval_minutes == 60
        assert config.llm.model == "llama3.2:3b"

    def test_env_overrides_newsdata_api_key(self):
        """Test environment variable overrides newsdata API key."""
        test_key = "env-newsdata-key"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({}, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"NEWSDATA_API_KEY": test_key}):
                config = Config.load(Path(temp_path))
                assert config.news_sources["newsdata"]["api_key"] == test_key
        finally:
            os.unlink(temp_path)
            if "NEWSDATA_API_KEY" in os.environ:
                del os.environ["NEWSDATA_API_KEY"]

    def test_env_overrides_ollama_model(self):
        """Test environment variable overrides Ollama model."""
        test_model = "gemma3:latest"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({}, f)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"OLLAMA_MODEL": test_model}):
                config = Config.load(Path(temp_path))
                assert config.llm.model == test_model
        finally:
            os.unlink(temp_path)
            if "OLLAMA_MODEL" in os.environ:
                del os.environ["OLLAMA_MODEL"]

    def test_env_overrides_twitter_credentials(self):
        """Test environment variables override Twitter credentials."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({}, f)
            temp_path = f.name

        try:
            with patch.dict(
                os.environ,
                {
                    "TWITTER_API_KEY": "env-api-key",
                    "TWITTER_API_SECRET": "env-api-secret",
                },
            ):
                config = Config.load(Path(temp_path))
                assert config.social.twitter.api_key == "env-api-key"
                assert config.social.twitter.api_secret == "env-api-secret"
        finally:
            os.unlink(temp_path)
            for key in ["TWITTER_API_KEY", "TWITTER_API_SECRET"]:
                if key in os.environ:
                    del os.environ[key]

    def test_env_overrides_facebook_credentials(self):
        """Test environment variables override Facebook credentials."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({}, f)
            temp_path = f.name

        try:
            with patch.dict(
                os.environ,
                {
                    "FACEBOOK_PAGE_ACCESS_TOKEN": "env-fb-token",
                    "FACEBOOK_PAGE_ID": "env-fb-id",
                },
            ):
                config = Config.load(Path(temp_path))
                assert config.social.facebook.page_access_token == "env-fb-token"
                assert config.social.facebook.page_id == "env-fb-id"
        finally:
            os.unlink(temp_path)
            for key in ["FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"]:
                if key in os.environ:
                    del os.environ[key]

    def test_extra_fields_ignored(self):
        """Test that extra fields in YAML are ignored."""
        config_data = {
            "unknown_field": "should be ignored",
            "another_unknown": 123,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = Config.load(Path(temp_path))
            assert not hasattr(config, "unknown_field")
        finally:
            os.unlink(temp_path)
