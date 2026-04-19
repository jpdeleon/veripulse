"""Configuration management for Veripulse."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

load_dotenv()


class DatabaseConfig(BaseModel):
    path: str = "data/veripulse.db"
    echo: bool = False


class NewsAPIConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""


class RSSFeed(BaseModel):
    url: str
    category: str = "general"


class RSSConfig(BaseModel):
    enabled: bool = True
    feeds: list[RSSFeed] = []


class ScrapingConfig(BaseModel):
    interval_minutes: int = 60
    max_articles_per_run: int = 50
    timeout_seconds: int = 30
    retry_attempts: int = 3


class LLMConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    host: str = ""  # SSH hostname from ~/.ssh/config; tunnels Ollama over SSH when set
    model: str = "qwen3.5:latest"
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout_seconds: int = 120


class EmbeddingsConfig(BaseModel):
    model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    device: str = "cpu"


class TwitterConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_secret: str = ""


class FacebookConfig(BaseModel):
    enabled: bool = False
    page_access_token: str = ""
    page_id: str = ""


class SocialConfig(BaseModel):
    twitter: TwitterConfig = Field(default_factory=TwitterConfig)
    facebook: FacebookConfig = Field(default_factory=FacebookConfig)


class EditorialConfig(BaseModel):
    auto_generate_summary: bool = False
    require_full_review: bool = True
    max_article_age_hours: int = 24


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "data/veripulse.log"
    rotation: str = "100 MB"
    retention: str = "30 days"


class Config(BaseSettings):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    news_sources: dict = Field(default_factory=dict)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    social: SocialConfig = Field(default_factory=SocialConfig)
    editorial: EditorialConfig = Field(default_factory=EditorialConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        cls._apply_env_overrides(data)
        return cls(**data)

    @classmethod
    def _apply_env_overrides(cls, data: dict) -> None:
        if "news_sources" not in data:
            data["news_sources"] = {}

        ns = data["news_sources"]

        if "newsdata" not in ns:
            ns["newsdata"] = {}
        ns["newsdata"]["api_key"] = os.environ.get(
            "NEWSDATA_API_KEY", ns["newsdata"].get("api_key", "")
        )

        if "newsapi" not in ns:
            ns["newsapi"] = {}
        ns["newsapi"]["api_key"] = os.environ.get(
            "NEWSAPI_API_KEY", ns["newsapi"].get("api_key", "")
        )

        if "llm" not in data:
            data["llm"] = {}
        data["llm"]["base_url"] = os.environ.get(
            "OLLAMA_BASE_URL", data["llm"].get("base_url", "http://localhost:11434")
        )
        data["llm"]["model"] = os.environ.get(
            "OLLAMA_MODEL", data["llm"].get("model", "llama3.2:3b")
        )
        data["llm"]["host"] = os.environ.get(
            "OLLAMA_SSH_HOST", data["llm"].get("host", "")
        )

        if "social" not in data:
            data["social"] = {"twitter": {}, "facebook": {}}

        tw = data["social"].get("twitter", {})
        tw["api_key"] = os.environ.get("TWITTER_API_KEY", tw.get("api_key", ""))
        tw["api_secret"] = os.environ.get("TWITTER_API_SECRET", tw.get("api_secret", ""))
        tw["access_token"] = os.environ.get("TWITTER_ACCESS_TOKEN", tw.get("access_token", ""))
        tw["access_secret"] = os.environ.get("TWITTER_ACCESS_SECRET", tw.get("access_secret", ""))

        fb = data["social"].get("facebook", {})
        fb["page_access_token"] = os.environ.get(
            "FACEBOOK_PAGE_ACCESS_TOKEN", fb.get("page_access_token", "")
        )
        fb["page_id"] = os.environ.get("FACEBOOK_PAGE_ID", fb.get("page_id", ""))

    class Config:
        extra = "ignore"


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.load()
    return _config
