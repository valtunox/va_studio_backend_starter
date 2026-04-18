"""
Analytics Collectors

Data collection utilities for analytics.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.core.redis import redis_client
from app.core.logger import get_logger


logger = get_logger(__name__)


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self):
        self._prefix = "metrics:"

    async def increment(self, metric_name: str, value: int = 1) -> None:
        """Increment a metric counter."""
        try:
            key = f"{self._prefix}counter:{metric_name}"
            await redis_client.client.incrby(key, value)
        except Exception as e:
            logger.warning(f"Failed to increment metric {metric_name}: {e}")

    async def gauge(self, metric_name: str, value: float) -> None:
        """Set a gauge metric value."""
        try:
            key = f"{self._prefix}gauge:{metric_name}"
            await redis_client.set(key, str(value))
        except Exception as e:
            logger.warning(f"Failed to set gauge {metric_name}: {e}")

    async def timing(self, metric_name: str, duration_ms: float) -> None:
        """Record a timing metric."""
        try:
            key = f"{self._prefix}timing:{metric_name}"
            await redis_client.client.lpush(key, str(duration_ms))
            await redis_client.client.ltrim(key, 0, 999)  # Keep last 1000
        except Exception as e:
            logger.warning(f"Failed to record timing {metric_name}: {e}")

    async def get_counter(self, metric_name: str) -> int:
        """Get counter value."""
        try:
            key = f"{self._prefix}counter:{metric_name}"
            value = await redis_client.get(key)
            return int(value) if value else 0
        except Exception:
            return 0

    async def get_gauge(self, metric_name: str) -> Optional[float]:
        """Get gauge value."""
        try:
            key = f"{self._prefix}gauge:{metric_name}"
            value = await redis_client.get(key)
            return float(value) if value else None
        except Exception:
            return None

    async def get_timing_stats(self, metric_name: str) -> Dict[str, float]:
        """Get timing statistics."""
        try:
            key = f"{self._prefix}timing:{metric_name}"
            values = await redis_client.client.lrange(key, 0, -1)
            if not values:
                return {}

            float_values = [float(v) for v in values]
            return {
                "count": len(float_values),
                "min": min(float_values),
                "max": max(float_values),
                "avg": sum(float_values) / len(float_values),
            }
        except Exception:
            return {}


class EventCollector:
    """Collects analytics events."""

    def __init__(self):
        self._prefix = "events:"

    async def collect(
        self,
        event_type: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """Collect an event."""
        event = {
            "type": event_type,
            "data": data,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            date_key = datetime.now().strftime("%Y%m%d")
            key = f"{self._prefix}{event_type}:{date_key}"
            await redis_client.client.lpush(key, str(event))
            await redis_client.client.expire(key, 86400 * 30)  # 30 days
        except Exception as e:
            logger.warning(f"Failed to collect event {event_type}: {e}")

    async def get_events(
        self,
        event_type: str,
        date: str,
        limit: int = 100,
    ) -> list:
        """Get events for a specific type and date."""
        try:
            key = f"{self._prefix}{event_type}:{date}"
            events = await redis_client.client.lrange(key, 0, limit - 1)
            return [eval(e) for e in events]  # Note: Use JSON in production
        except Exception:
            return []


# Global instances
metrics_collector = MetricsCollector()
event_collector = EventCollector()
