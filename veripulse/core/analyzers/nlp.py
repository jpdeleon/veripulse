"""Article analyzers for categorization, sentiment, and importance scoring."""

import re
from typing import Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger

from veripulse.core.config import get_config
from veripulse.core.database import Article


CATEGORY_KEYWORDS = {
    "politics": [
        "government",
        "senate",
        "congress",
        "politician",
        "election",
        "vote",
        "president",
        "minister",
        "lawmaker",
        "bill",
        "legislation",
        "policy",
        "marcos",
        "duterte",
        " PNoy",
        "arroyo",
        "estrada",
        "bongbong",
        "bureau",
        "department",
        "DILG",
        "DOJ",
        "COMELEC",
    ],
    "economy": [
        "economy",
        "economic",
        "business",
        "trade",
        "market",
        "stock",
        "inflation",
        "GDP",
        " peso",
        "dollar",
        "investment",
        "finance",
        "BSP",
        "central bank",
        "Bangko Sentral",
        "tax",
        "tariff",
    ],
    "technology": [
        "tech",
        "technology",
        "digital",
        "AI",
        "app",
        "software",
        "startup",
        "innovation",
        "cyber",
        "data",
        "internet",
        "online",
    ],
    "sports": [
        "sports",
        "basketball",
        "football",
        "volleyball",
        "MMA",
        "boxing",
        "PBA",
        "UAAP",
        "NCAA",
        "Olympics",
        "athlete",
        "tournament",
    ],
    "entertainment": [
        "entertainment",
        "movie",
        "music",
        "celebrity",
        "celeb",
        "actor",
        "actress",
        "singer",
        "concert",
        "showbiz",
        "teleserye",
        "film",
    ],
    "crime": [
        "crime",
        "murder",
        "killing",
        "robbery",
        "theft",
        "drug",
        "narcotics",
        "pnp",
        "police",
        "investigation",
        "suspect",
        "arrest",
        "warrant",
    ],
    "disaster": [
        "typhoon",
        "earthquake",
        "flood",
        "landslide",
        "eruption",
        "disaster",
        "calamity",
        "evacuation",
        "NDRRMC",
        "PAGASA",
        "signal",
        "rainfall",
    ],
    "health": [
        "health",
        "medical",
        "hospital",
        "disease",
        "virus",
        "COVID",
        "vaccine",
        "DOH",
        "healthcare",
        "doctor",
        "patient",
        "treatment",
    ],
    "education": [
        "education",
        "school",
        "university",
        "college",
        "student",
        "teacher",
        "CHED",
        "DepEd",
        "class",
        "exam",
        "graduation",
        "enrollment",
    ],
    "world": [
        "international",
        "foreign",
        "abroad",
        "US",
        "China",
        "Japan",
        "UN",
        "ASEAN",
        "diplomat",
        "summit",
        "treaty",
        "overseas",
        "OFW",
    ],
}


class Categorizer:
    def categorize(self, article: Article) -> str:
        text = f"{article.title} {article.content or ''}".lower()

        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            scores[category] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        return max(scores, key=scores.get)  # type: ignore

    def categorize_from_text(self, title: str, content: str = "") -> str:
        text = f"{title} {content}".lower()

        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            scores[category] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        return max(scores, key=scores.get)  # type: ignore


class SentimentAnalyzer:
    POSITIVE_WORDS = {
        "good",
        "great",
        "excellent",
        "amazing",
        "wonderful",
        "positive",
        "success",
        "successful",
        "achieve",
        "achievement",
        "growth",
        "grow",
        "improve",
        "improvement",
        "progress",
        "advance",
        "breakthrough",
        "win",
        "victory",
        "triumph",
        "celebrate",
        "proud",
        "honor",
        "help",
        "support",
        "approve",
        "agreement",
        "deal",
        "sign",
    }

    NEGATIVE_WORDS = {
        "bad",
        "terrible",
        "awful",
        "horrible",
        "negative",
        "poor",
        "fail",
        "failure",
        "decline",
        "crisis",
        "problem",
        "issue",
        "scandal",
        "controversy",
        "corrupt",
        "corruption",
        "deadly",
        "death",
        "kill",
        "killed",
        "attack",
        "threat",
        "warn",
        "deny",
        "reject",
        "protest",
        "oppose",
        "cancel",
        "suspend",
    }

    def analyze(self, text: str) -> tuple[str, float]:
        text_lower = text.lower()
        words = re.findall(r"\b\w+\b", text_lower)

        pos_count = sum(1 for w in words if w in self.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in self.NEGATIVE_WORDS)
        total = pos_count + neg_count

        if total == 0:
            return "neutral", 0.0

        pos_ratio = pos_count / total

        if pos_ratio > 0.6:
            sentiment = "positive"
        elif pos_ratio < 0.4:
            sentiment = "negative"
        else:
            sentiment = "mixed"

        score = (pos_ratio - 0.5) * 2

        return sentiment, round(score, 3)

    def analyze_article(self, article: Article) -> tuple[str, float]:
        text = f"{article.title} {article.content or ''}"
        return self.analyze(text)


class ImportanceScorer:
    def __init__(self):
        self.boost_keywords = {
            "breaking",
            "urgent",
            "exclusive",
            "developing",
            "just in",
            "announcement",
            "announces",
            "declared",
            "confirms",
            "confirms",
            "senate",
            "congress",
            "president",
            "prime minister",
        }
        self.dampen_keywords = {"opinion", "analysis", "commentary", "editorial", "column"}

    def calculate(self, article: Article, all_articles: list[Article] = None) -> float:
        score = 0.5
        text_lower = (article.title + " " + (article.content or "")).lower()

        for kw in self.boost_keywords:
            if kw in text_lower:
                score += 0.1

        for kw in self.dampen_keywords:
            if kw in text_lower:
                score -= 0.1

        if article.sentiment == "negative":
            score += 0.05
        elif article.sentiment == "positive":
            score -= 0.02

        if article.category in ["politics", "economy", "disaster", "crime"]:
            score += 0.1

        if all_articles:
            recent_count = sum(1 for a in all_articles if a.category == article.category)
            if recent_count > 5:
                score -= 0.05

        return max(0.0, min(1.0, score))


class TrendingDetector:
    def __init__(self):
        self.category_history: dict[str, list[tuple[str, float]]] = {}

    def calculate_trending_score(self, article: Article, recent_articles: list[Article]) -> float:
        if not recent_articles:
            return 0.0

        category = article.category or "general"

        if category not in self.category_history:
            self.category_history[category] = []

        similar_count = 0
        title_words = set(re.findall(r"\b\w+\b", article.title.lower()))

        for recent in recent_articles[:20]:
            if recent.id == article.id:
                continue
            recent_words = set(re.findall(r"\b\w+\b", recent.title.lower()))
            overlap = len(title_words & recent_words)
            if overlap >= 2:
                similar_count += 1

        score = min(1.0, similar_count / 5.0)

        return round(score, 2)
