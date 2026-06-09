import json
from datetime import datetime
from typing import List, Optional

from redis import Redis

from app.ai.repositories.schemas import ChatRecord


class RedisChatMemoryCache:
    """Redis short-term memory cache.

    Stores recent chat messages in a Redis List.
    Database remains the source of truth.
    """

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "memory_ai",
        max_messages: int = 20,
        ttl_seconds: int = 60 * 60 * 24,
    ):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds

    def _key(self, *, session_id: str, tenant_id: Optional[str] = None) -> str:
        tenant = tenant_id or "default"
        return f"{self.key_prefix}:chat:{tenant}:{session_id}"

    def load_history(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ChatRecord]:
        key = self._key(session_id=session_id, tenant_id=tenant_id)
        raw_items = self.redis.lrange(key, 0, -1)

        records: List[ChatRecord] = []
        for raw in raw_items:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            item = json.loads(raw)
            timestamp = item.get("timestamp")

            records.append(
                ChatRecord(
                    role=item["role"],
                    content=item["content"],
                    timestamp=datetime.fromisoformat(timestamp)
                    if timestamp
                    else datetime.now(),
                )
            )

        return records

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        tenant_id: Optional[str] = None,
    ) -> None:
        key = self._key(session_id=session_id, tenant_id=tenant_id)

        payload = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        self.redis.rpush(key, json.dumps(payload, ensure_ascii=False))
        self.redis.ltrim(key, -self.max_messages, -1)
        self.redis.expire(key, self.ttl_seconds)

    def seed_history(
        self,
        *,
        session_id: str,
        history: List[ChatRecord],
        tenant_id: Optional[str] = None,
    ) -> None:
        key = self._key(session_id=session_id, tenant_id=tenant_id)
        self.redis.delete(key)

        for record in history[-self.max_messages:]:
            payload = {
                "role": record.role,
                "content": record.content,
                "timestamp": record.timestamp.isoformat(),
            }
            self.redis.rpush(key, json.dumps(payload, ensure_ascii=False))

        self.redis.expire(key, self.ttl_seconds)

    def delete_session(
        self,
        *,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> None:
        key = self._key(session_id=session_id, tenant_id=tenant_id)
        self.redis.delete(key)