"""Database models for Veripulse."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ArticleStatus(str, Enum):
    RAW = "raw"
    ANALYZED = "analyzed"
    GENERATED = "generated"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    POSTED = "posted"
    FAILED = "failed"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class BaseModel(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Source(BaseModel):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(100))
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Article(BaseModel):
    __tablename__ = "articles"

    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default=ArticleStatus.RAW.value)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)
    trending_score: Mapped[float] = mapped_column(Float, default=0.0)

    source: Mapped["Source"] = relationship(back_populates="articles")
    commentary: Mapped[Optional["Commentary"]] = relationship(
        back_populates="article", uselist=False
    )
    social_posts: Mapped[list["SocialPost"]] = relationship(back_populates="article")

    __table_args__ = (
        Index("ix_articles_status", "status"),
        Index("ix_articles_published", "published_at"),
        Index("ix_articles_importance", "importance_score"),
    )


class Commentary(BaseModel):
    __tablename__ = "commentary"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True)
    headline: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    commentary_text: Mapped[str] = mapped_column(Text)
    key_takeaways: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bias_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fact_check_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")

    article: Mapped["Article"] = relationship(back_populates="commentary")


class SocialPost(BaseModel):
    __tablename__ = "social_posts"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    platform: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    post_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    engagement: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    article: Mapped["Article"] = relationship(back_populates="social_posts")

    __table_args__ = (
        Index("ix_social_posts_scheduled", "scheduled_at"),
        Index("ix_social_posts_status", "status"),
    )


class Topic(BaseModel):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_topics_active", "is_active"),)


def init_db(db_path: str) -> tuple:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal
