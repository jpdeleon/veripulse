"""Social media publishers for X, Facebook, etc."""

from datetime import datetime
from typing import Optional
import httpx
from loguru import logger

from veripulse.core.config import get_config
from veripulse.core.database import Article, SocialPost


class BasePublisher:
    platform: str = "base"

    def __init__(self):
        self.config = get_config()

    async def post(self, content: str, article: Article) -> dict:
        raise NotImplementedError

    def _create_post_record(
        self, article: Article, content: str, platform: str, **kwargs
    ) -> SocialPost:
        return SocialPost(
            article_id=article.id,
            platform=platform,
            content=content,
            hashtags=kwargs.get("hashtags"),
            post_url=kwargs.get("post_url"),
            status="posted",
            posted_at=datetime.utcnow(),
        )


class TwitterPublisher(BasePublisher):
    platform = "twitter"

    def __init__(self):
        super().__init__()
        self.twitter_config = self.config.social.twitter
        self.enabled = self.twitter_config.enabled

    async def post(self, content: str, article: Article) -> dict:
        if not self.enabled:
            return {"success": False, "error": "Twitter integration not enabled"}

        try:
            payload = {
                "text": content,
            }

            headers = {
                "Authorization": f"Bearer {self.twitter_config.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.twitter.com/2/tweets",
                    json=payload,
                    headers=headers,
                )

                if response.status_code == 201:
                    data = response.json()
                    post_url = f"https://twitter.com/user/status/{data['data']['id']}"
                    return {"success": True, "post_url": post_url, "post_id": data["data"]["id"]}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Twitter post failed: {e}")
            return {"success": False, "error": str(e)}

    async def schedule(self, content: str, article: Article, scheduled_at: datetime) -> dict:
        return {
            "success": False,
            "error": "Scheduling not implemented for Twitter (use external scheduler)",
        }


class FacebookPublisher(BasePublisher):
    platform = "facebook"

    def __init__(self):
        super().__init__()
        self.fb_config = self.config.social.facebook
        self.enabled = self.fb_config.enabled
        self.page_id = self.fb_config.page_id

    async def post(self, content: str, article: Article) -> dict:
        if not self.enabled:
            return {"success": False, "error": "Facebook integration not enabled"}

        try:
            payload = {
                "message": content,
                "link": article.url,
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://graph.facebook.com/v18.0/{self.page_id}/feed",
                    params={"access_token": self.fb_config.page_access_token},
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    post_url = (
                        f"https://facebook.com/{self.page_id}/posts/{data['id'].split('_')[-1]}"
                    )
                    return {"success": True, "post_url": post_url, "post_id": data["id"]}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            logger.error(f"Facebook post failed: {e}")
            return {"success": False, "error": str(e)}

    async def schedule(self, content: str, article: Article, scheduled_at: datetime) -> dict:
        return {"success": False, "error": "Use Facebook's native scheduling or external tool"}


class PublisherFactory:
    _publishers = {
        "twitter": TwitterPublisher,
        "x": TwitterPublisher,
        "facebook": FacebookPublisher,
    }

    @classmethod
    def get_publisher(cls, platform: str) -> Optional[BasePublisher]:
        publisher_class = cls._publishers.get(platform.lower())
        if publisher_class:
            return publisher_class()
        return None

    @classmethod
    def get_all_publishers(cls) -> list[BasePublisher]:
        return [pc() for pc in cls._publishers.values()]
