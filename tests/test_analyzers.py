"""Tests for the NLP analyzers."""


from veripulse.core.analyzers.nlp import (
    CATEGORY_KEYWORDS,
    Categorizer,
    ImportanceScorer,
    SentimentAnalyzer,
    TrendingDetector,
)


class TestCategorizer:
    """Tests for the Categorizer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.categorizer = Categorizer()

    def test_categorize_politics(self):
        """Test categorization of politics article."""
        title = "Senate passes new cybersecurity law"
        content = "The Philippine Senate voted to pass a new cybersecurity bill."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "politics"

    def test_categorize_economy(self):
        """Test categorization of economy article."""
        title = "BSP keeps interest rates steady"
        content = "The Bangko Sentral ng Pilipinas maintained its interest rate policy."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "economy"

    def test_categorize_technology(self):
        """Test categorization of technology article."""
        title = "New AI startup raises funding"
        content = "A Manila-based AI startup has raised $10 million in Series A funding."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "technology"

    def test_categorize_sports(self):
        """Test categorization of sports article."""
        title = "Gilas Pilipinas wins in FIBA Asia Cup"
        content = "The Philippine basketball team secured a victory in the tournament."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "sports"

    def test_categorize_entertainment(self):
        """Test categorization of entertainment article."""
        title = "New Netflix series features Filipino actors"
        content = "A celebrity-led drama is set to premiere next month."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "entertainment"

    def test_categorize_crime(self):
        """Test categorization of crime article."""
        title = "PNP arrests suspects in robbery case"
        content = "Police have arrested several suspects following investigations."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "crime"

    def test_categorize_disaster(self):
        """Test categorization of disaster article."""
        title = "Typhoon Egay affects thousands in Luzon"
        content = "PAGASA has raised signal warnings as the typhoon approaches."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "disaster"

    def test_categorize_health(self):
        """Test categorization of health article."""
        title = "DOH announces new vaccine rollout"
        content = "The Department of Health will begin distributing vaccines nationwide."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "health"

    def test_categorize_education(self):
        """Test categorization of education article."""
        title = "DepEd announces school opening date"
        content = "Classes will begin in August according to the education department."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "education"

    def test_categorize_world(self):
        """Test categorization of world news article."""
        title = "US and China hold trade talks"
        content = "American officials met with Chinese counterparts in Geneva."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "world"

    def test_categorize_general(self):
        """Test categorization returns general when no keywords match."""
        title = "Random article about nothing"
        content = "This is a very generic article with no specific topics."
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "general"

    def test_categorize_case_insensitive(self):
        """Test categorization is case insensitive."""
        title = "SENATE passes bill"
        content = "THE CONGRESS voted"
        category = self.categorizer.categorize_from_text(title, content)
        assert category == "politics"

    def test_categorize_article_object(self, sample_article):
        """Test categorization from Article object."""
        sample_article.title = "Presidential election results announced"
        category = self.categorizer.categorize(sample_article)
        assert category == "politics"

    def test_categorize_empty_content(self):
        """Test categorization with empty content."""
        category = self.categorizer.categorize_from_text("Title Only", "")
        assert category == "general"


class TestSentimentAnalyzer:
    """Tests for the SentimentAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = SentimentAnalyzer()

    def test_positive_sentiment(self):
        """Test positive sentiment detection."""
        text = "This is great! Excellent growth and wonderful achievements."
        sentiment, score = self.analyzer.analyze(text)
        assert sentiment == "positive"
        assert score > 0

    def test_negative_sentiment(self):
        """Test negative sentiment detection."""
        text = "This is terrible. Poor performance and awful decline."
        sentiment, score = self.analyzer.analyze(text)
        assert sentiment == "negative"
        assert score < 0

    def test_neutral_sentiment(self):
        """Test neutral sentiment when balanced."""
        text = "The meeting happened today. People attended."
        sentiment, score = self.analyzer.analyze(text)
        assert sentiment == "neutral"
        assert score == 0.0

    def test_mixed_sentiment(self):
        """Test mixed sentiment detection."""
        text = "Good progress but terrible delays. Success mixed with failure."
        sentiment, score = self.analyzer.analyze(text)
        assert sentiment == "mixed"

    def test_sentiment_score_bounds(self):
        """Test sentiment score is between -1 and 1."""
        positive_text = " ".join(["excellent"] * 20)
        sentiment, score = self.analyzer.analyze(positive_text)
        assert -1.0 <= score <= 1.0

    def test_sentiment_article_object(self, sample_article):
        """Test sentiment analysis from Article object."""
        sample_article.content = "The economy shows wonderful growth and progress."
        sentiment, score = self.analyzer.analyze_article(sample_article)
        assert sentiment == "positive"


class TestImportanceScorer:
    """Tests for the ImportanceScorer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = ImportanceScorer()

    def test_default_score(self, sample_article):
        """Test importance score calculation.
        Sample article has economy category (+0.1) and contains 'announces' (+0.1).
        """
        sample_article.sentiment = "neutral"
        score = self.scorer.calculate(sample_article)
        assert score == 0.5 + 0.1 + 0.1

    def test_boost_keywords(self, sample_article):
        """Test importance boost for breaking/urgent keywords."""
        sample_article.title = "BREAKING: Senate announces new law"
        sample_article.sentiment = "neutral"
        sample_article.category = "general"
        score = self.scorer.calculate(sample_article)
        assert score > 0.5

    def test_dampen_keywords(self, sample_article):
        """Test importance reduction for opinion/editorial keywords."""
        sample_article.title = "Opinion: Analysis of the new policy"
        sample_article.sentiment = "neutral"
        sample_article.category = "general"
        score = self.scorer.calculate(sample_article)
        assert score < 0.5

    def test_negative_sentiment_boost(self, sample_article):
        """Test that negative sentiment slightly increases importance."""
        sample_article.sentiment = "negative"
        sample_article.category = "general"
        score = self.scorer.calculate(sample_article)
        assert score > 0.5

    def test_positive_sentiment_dampen(self, sample_article):
        """Test that positive sentiment slightly decreases importance.
        Economy category (+0.1), announces (+0.1) and positive sentiment (-0.02).
        """
        sample_article.sentiment = "positive"
        score = self.scorer.calculate(sample_article)
        assert score == 0.5 + 0.1 + 0.1 - 0.02

    def test_category_boost(self, sample_article):
        """Test importance boost for high-priority categories."""
        sample_article.sentiment = "neutral"
        sample_article.category = "politics"
        score = self.scorer.calculate(sample_article)
        assert score > 0.5

    def test_score_bounds(self, sample_article):
        """Test importance score stays within 0-1 bounds."""
        sample_article.title = "BREAKING URGENT DEVELOPING ANNOUNCEMENT"
        sample_article.sentiment = "negative"
        sample_article.category = "politics"
        score = self.scorer.calculate(sample_article)
        assert 0.0 <= score <= 1.0

    def test_trending_dampening(self, sample_article, sample_articles):
        """Test importance reduction when category has >5 articles.
        Sports has only 1 article in sample_articles, so no dampening.
        """
        sports_article = sample_articles[1]
        sports_article.sentiment = "neutral"
        score = self.scorer.calculate(sports_article, sample_articles)
        assert score == 0.5


class TestTrendingDetector:
    """Tests for the TrendingDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = TrendingDetector()

    def test_no_recent_articles(self, sample_article):
        """Test trending score with no recent articles."""
        score = self.detector.calculate_trending_score(sample_article, [])
        assert score == 0.0

    def test_trending_with_similar_articles(self, sample_article, sample_articles):
        """Test trending score increases with similar articles."""
        sample_article.title = "PBA Teams Compete for Championship"
        score = self.detector.calculate_trending_score(sample_article, sample_articles)
        assert score > 0.0

    def test_not_trending_unique_article(self, sample_article, sample_articles):
        """Test trending score is low for unique articles."""
        sample_article.title = "Unique Random Topic XYZ"
        score = self.detector.calculate_trending_score(sample_article, sample_articles)
        assert score <= 1.0

    def test_category_history_tracking(self, sample_article, sample_articles):
        """Test category history is maintained."""
        self.detector.calculate_trending_score(sample_article, sample_articles)
        assert sample_article.category in self.detector.category_history

    def test_max_trending_score(self, sample_article, sample_articles):
        """Test trending score maxes out at 1.0."""
        for article in sample_articles[:5]:
            article.title = "PBA Finals Championship Game"
        score = self.detector.calculate_trending_score(sample_articles[0], sample_articles)
        assert score <= 1.0


class TestCategoryKeywords:
    """Tests for CATEGORY_KEYWORDS coverage."""

    def test_all_categories_have_keywords(self):
        """Test all expected categories have keywords defined."""
        expected_categories = [
            "politics",
            "economy",
            "technology",
            "sports",
            "entertainment",
            "crime",
            "disaster",
            "health",
            "education",
            "world",
        ]
        for category in expected_categories:
            assert category in CATEGORY_KEYWORDS
            assert len(CATEGORY_KEYWORDS[category]) > 0

    def test_philippine_specific_keywords(self):
        """Test Philippine-specific keywords are present."""
        politics_kw = CATEGORY_KEYWORDS["politics"]
        assert any("marcos" in kw.lower() for kw in politics_kw)
        assert any("senate" in kw.lower() for kw in politics_kw)

        economy_kw = CATEGORY_KEYWORDS["economy"]
        assert any("bsp" in kw.lower() for kw in economy_kw)

        disaster_kw = CATEGORY_KEYWORDS["disaster"]
        assert any("ndrrmc" in kw.lower() for kw in disaster_kw)
        assert any("pagasa" in kw.lower() for kw in disaster_kw)
