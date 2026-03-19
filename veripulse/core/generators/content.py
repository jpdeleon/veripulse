"""LLM-based content generators for summaries, commentary, and social posts."""

import json
import re
from typing import Optional
import httpx
from loguru import logger

from veripulse.core.config import get_config
from veripulse.core.database import Article


def extract_json(text: str) -> str | None:
    """Extract first JSON object from text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return None


class LLMClient:
    def __init__(self):
        self.config = get_config()
        self.base_url = self.config.llm.base_url
        self.model = self.config.llm.model
        self.temperature = self.config.llm.temperature
        self.max_tokens = self.config.llm.max_tokens
        self.timeout = self.config.llm.timeout_seconds

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except httpx.TimeoutException:
            logger.error("LLM request timed out")
            return ""
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return ""

    def check_connection(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False
                data = response.json()
                available_models = [m.get("name", "") for m in data.get("models", [])]
                if self.model not in available_models:
                    logger.warning(f"Model {self.model} not found. Available: {available_models}")
                return True
        except httpx.ConnectError:
            logger.error(f"Cannot connect to Ollama at {self.base_url}")
            return False
        except Exception as e:
            logger.error(f"Ollama connection check failed: {e}")
            return False


class Summarizer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def summarize(self, article: Article, max_length: int = 200) -> str:
        if not article.content:
            return article.summary or ""

        prompt = f"""Summarize the following news article in {max_length} words or less.
Focus on the key facts and main points.

Title: {article.title}
Content: {article.content[:3000]}

Provide a concise summary:"""

        system = "You are a professional news summarizer. Be accurate and objective."
        return await self.llm.generate(prompt, system)

    async def summarize_bilingual(self, article: Article, max_length: int = 150) -> str:
        if not article.content:
            return article.summary or ""

        prompt = f"""Sumamahin ang sumusunod na article sa {max_length} salita o mas kaunti.
Mag-focus sa mga pangunahing katotohanan at punto.

Title: {article.title}
Content: {article.content[:2000]}

Magbigay ng maikling summary sa Filipino/Tagalog:"""

        system = "Ikaw ay isang propesyonal na news summarizer. Maging accurate at objective. Sumulat sa Filipino/Tagalog."
        return await self.llm.generate(prompt, system)


class Commentator:
    FILIPINO_IDIOMS = {
        "positive": [
            " Kagandahang-loob",
            " sama ng loob",
            " pag-asa",
            " tiwala",
        ],
        "context": [
            "Sa lipunang Pilipino",
            "Sa konteksto ng Pilipinas",
            "Para sa mamamayan",
        ],
    }

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate_commentary(self, article: Article) -> dict:
        prompt = f"""Generate insightful commentary for this news article.
Include:
1. A catchy headline (if not provided)
2. Key takeaways (3 bullet points)
3. Context and implications
4. Any potential bias to note

Title: {article.title}
Content: {article.content[:3000]}
Category: {article.category}
Sentiment: {article.sentiment}

Format as JSON:
{{
    "headline": "...",
    "commentary": "...",
    "key_takeaways": ["...", "...", "..."],
    "bias_notes": "..."
}}"""

        system = """You are a thoughtful news analyst providing context and insights.
Be balanced, accurate, and consider multiple perspectives.
If discussing Philippine news, incorporate relevant cultural and political context."""

        response = await self.llm.generate(prompt, system)

        try:
            json_str = extract_json(response)
            if json_str:
                data = json.loads(json_str)
                return data
            return {
                "headline": None,
                "commentary": response,
                "key_takeaways": None,
                "bias_notes": None,
            }
        except json.JSONDecodeError:
            return {
                "headline": None,
                "commentary": response,
                "key_takeaways": None,
                "bias_notes": None,
            }

    async def generate_commentary_filipino(self, article: Article) -> dict:
        prompt = f"""Gumawa ng insightful commentary para sa news article na ito.
Isama ang:
1. Isang catchy na headline
2. Mga key takeaways (3 puntos)
3. Konteksto at implications
4. Anumang potential bias na dapat pansinin

Title: {article.title}
Content: {article.content[:2000]}
Category: {article.category}
Sentiment: {article.sentiment}

Format as JSON:
{{
    "headline": "...",
    "commentary": "...",
    "key_takeaways": ["...", "...", "..."],
    "bias_notes": "..."
}}"""

        system = """Ikaw ay isang maalam na news analyst na nagbibigay ng konteksto at insights.
Maging balanced, accurate, at isiping maraming perspectives.
Kung may kinalaman sa Pilipinas, isama ang relevant cultural at political context.
Sumulat sa Filipino/Tagalog."""

        response = await self.llm.generate(prompt, system)

        try:
            json_str = extract_json(response)
            if json_str:
                data = json.loads(json_str)
                return data
            return {
                "headline": None,
                "commentary": response,
                "key_takeaways": None,
                "bias_notes": None,
            }
        except json.JSONDecodeError:
            return {
                "headline": None,
                "commentary": response,
                "key_takeaways": None,
                "bias_notes": None,
            }


class SocialPostGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def generate_tweet(
        self, article: Article, commentary: str = "", include_hashtags: bool = True
    ) -> str:
        sentiment_indicator = {
            "positive": "✨",
            "negative": "📉",
            "mixed": "⚖️",
            "neutral": "📰",
        }.get(article.sentiment or "neutral", "📰")

        prompt = f"""Write a compelling tweet (max 280 characters) about this news.
Include an engaging hook, key info, and a link.

Title: {article.title}
Commentary: {commentary[:500] if commentary else article.summary or ""}

Format: {sentiment_indicator} [Engaging text] [URL]
Length: Under 280 characters"""

        if include_hashtags:
            prompt += "\nInclude 2-3 relevant hashtags."

        result = await self.llm.generate(prompt)
        return result[:280] if len(result) > 280 else result

    async def generate_facebook_post(
        self, article: Article, commentary: str = "", max_length: int = 500
    ) -> str:
        prompt = f"""Write a Facebook post about this news article.
Make it engaging, conversational, and encourage discussion.
Include a brief summary, your take, and a link.

Title: {article.title}
Commentary: {commentary[:1000] if commentary else article.summary or ""}

Length: Around {max_length} characters"""

        result = await self.llm.generate(prompt)

        if len(result) > max_length:
            result = result[: max_length - 3] + "..."

        result += f"\n\n🔗 {article.url}"
        return result

    async def generate_linkedin_post(self, article: Article, commentary: str = "") -> str:
        prompt = f"""Write a professional LinkedIn post about this news.
Focus on the professional/policy implications.
Include a brief summary and thoughtful commentary.

Title: {article.title}
Commentary: {commentary[:1000] if commentary else article.summary or ""}

Length: 200-500 characters"""

        result = await self.llm.generate(prompt)
        result += f"\n\n🔗 {article.url}"
        return result


class FactChecker:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def check_article(self, article: Article) -> dict:
        prompt = f"""Analyze this news article for potential credibility issues.
Check for:
1. Vague sourcing
2. Unverifiable claims
3. Potential misinformation red flags
4. Bias indicators

Title: {article.title}
Content: {article.content[:3000]}
Source: {article.source.name if article.source else "Unknown"}

Provide a brief analysis as JSON:
{{
    "credibility_score": 0.0-1.0,
    "red_flags": ["..."],
    "notes": "..."
}}"""

        system = """You are a fact-checking assistant. Be objective and thorough.
Provide low scores only when there are clear red flags.
Do not reject articles based on minor issues."""

        response = await self.llm.generate(prompt, system)

        try:
            json_str = extract_json(response)
            if json_str:
                data = json.loads(json_str)
                return data
            return {"credibility_score": 0.5, "red_flags": [], "notes": response}
        except json.JSONDecodeError:
            return {"credibility_score": 0.5, "red_flags": [], "notes": "Could not analyze"}
