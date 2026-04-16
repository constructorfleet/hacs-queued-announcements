"""Core queue manager for Queued Announcements."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ANNOUNCE_SERVICE,
    CONF_DEDUPE_MODE,
    CONF_SUMMARIZE_ON_FLUSH,
    CONF_TTL_MINUTES,
    CONF_WORK_HOURS_END,
    CONF_WORK_HOURS_START,
    DEDUPE_MODE_BOTH,
    DEDUPE_MODE_MESSAGE,
    DEDUPE_MODE_TAG,
    DEFAULT_TAG,
    DOMAIN,
)
from .storage import QueueStorage

_LOGGER = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """A single queued announcement."""

    id: str
    message: str
    tag: str
    created_at: str  # ISO-8601 string
    critical: bool

    @staticmethod
    def create(message: str, tag: str, critical: bool) -> QueueItem:
        return QueueItem(
            id=str(uuid.uuid4()),
            message=message,
            tag=tag,
            created_at=datetime.now(UTC).isoformat(),
            critical=critical,
        )

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> QueueItem:
        return QueueItem(
            id=data["id"],
            message=data["message"],
            tag=data.get("tag", DEFAULT_TAG),
            created_at=data["created_at"],
            critical=data.get("critical", False),
        )

    def is_expired(self, ttl_minutes: int | None) -> bool:
        """Return True if this item is older than ttl_minutes."""
        if ttl_minutes is None:
            return False
        created = datetime.fromisoformat(self.created_at)
        age_minutes = (datetime.now(UTC) - created).total_seconds() / 60
        return age_minutes > ttl_minutes


class QueueManager:
    """Manages the announcement queue."""

    def __init__(self, hass: HomeAssistant, config: dict, storage: QueueStorage) -> None:
        self._hass = hass
        self._config = config
        self._storage = storage
        self._queue: list[QueueItem] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def queue(self) -> list[QueueItem]:
        return list(self._queue)

    @property
    def queue_count(self) -> int:
        return len(self._queue)

    def is_work_hours(self) -> bool:
        """Return True when the current local time falls within work hours."""
        now = datetime.now().time()
        start_raw = self._config.get(CONF_WORK_HOURS_START, "09:00:00")
        end_raw = self._config.get(CONF_WORK_HOURS_END, "17:00:00")
        start = _parse_time(start_raw)
        end = _parse_time(end_raw)
        if start <= end:
            return start <= now < end
        # Overnight span
        return now >= start or now < end

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load persisted queue from storage."""
        raw = await self._storage.async_load()
        self._queue = [QueueItem.from_dict(d) for d in raw]
        _LOGGER.debug("Manager loaded %d item(s)", len(self._queue))

    async def _async_save(self) -> None:
        await self._storage.async_save([item.as_dict() for item in self._queue])

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    async def async_enqueue(
        self,
        message: str,
        tag: str = DEFAULT_TAG,
        critical: bool = False,
    ) -> None:
        """Add a message to the queue or announce it immediately."""
        _LOGGER.debug("enqueue called: message=%r tag=%r critical=%s", message, tag, critical)

        if critical:
            _LOGGER.debug("Critical announcement – delivering immediately")
            await self._async_announce(message)
            return

        if not self.is_work_hours():
            _LOGGER.debug("Outside work hours – delivering immediately")
            await self._async_announce(message)
            return

        # Deduplication
        if self._is_duplicate(message, tag):
            _LOGGER.debug(
                "Duplicate detected (mode=%s) for tag=%r – skipping enqueue",
                self._config.get(CONF_DEDUPE_MODE, DEDUPE_MODE_BOTH),
                tag,
            )
            return

        item = QueueItem.create(message=message, tag=tag, critical=critical)
        self._queue.append(item)
        await self._async_save()
        _LOGGER.debug("Enqueued item id=%s tag=%r", item.id, tag)
        self._async_fire_state_changed()

    async def async_dequeue(self, tag: str) -> int:
        """Remove all items with the given tag. Returns removed count."""
        before = len(self._queue)
        self._queue = [i for i in self._queue if i.tag != tag]
        removed = before - len(self._queue)
        if removed:
            await self._async_save()
            self._async_fire_state_changed()
        _LOGGER.debug("Dequeued %d item(s) with tag=%r", removed, tag)
        return removed

    async def async_flush(self, force: bool = False) -> None:
        """Replay all valid queued items then clear the queue."""
        if self.is_work_hours() and not force:
            _LOGGER.debug("flush called during work hours without force – skipping")
            return

        ttl = self._config.get(CONF_TTL_MINUTES)
        valid = [i for i in self._queue if not i.is_expired(ttl)]
        expired = len(self._queue) - len(valid)
        if expired:
            _LOGGER.debug("Dropping %d expired item(s)", expired)

        if not valid:
            _LOGGER.debug("Nothing to flush")
            self._queue = []
            await self._async_save()
            return

        if self._config.get(CONF_SUMMARIZE_ON_FLUSH, False):
            summary = f"You have {len(valid)} queued announcement(s)."
            await self._async_announce(summary)

        for item in valid:
            _LOGGER.debug("Flushing item id=%s tag=%r", item.id, item.tag)
            await self._async_announce(item.message)

        self._queue = []
        await self._async_save()
        self._async_fire_state_changed()
        _LOGGER.debug("Flush complete – %d item(s) announced", len(valid))

    async def async_clear(self) -> None:
        """Remove all items without announcing."""
        count = len(self._queue)
        self._queue = []
        await self._async_save()
        self._async_fire_state_changed()
        _LOGGER.debug("Queue cleared (%d item(s) removed)", count)

    def async_peek(self) -> list[dict]:
        """Return a snapshot of the current queue."""
        return [item.as_dict() for item in self._queue]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_duplicate(self, message: str, tag: str) -> bool:
        mode = self._config.get(CONF_DEDUPE_MODE, DEDUPE_MODE_BOTH)
        for existing in self._queue:
            if mode == DEDUPE_MODE_TAG and existing.tag == tag:
                return True
            if mode == DEDUPE_MODE_MESSAGE and existing.message == message:
                return True
            if mode == DEDUPE_MODE_BOTH and (existing.tag == tag or existing.message == message):
                return True
        return False

    async def _async_announce(self, message: str) -> None:
        """Call the configured announce service."""
        service_str = self._config.get(CONF_ANNOUNCE_SERVICE, "")
        if not service_str:
            _LOGGER.warning("No announce_service configured – cannot announce: %r", message)
            return
        parts = service_str.split(".", 1)
        if len(parts) != 2:
            _LOGGER.error("Invalid announce_service format: %r", service_str)
            return
        domain, service = parts
        _LOGGER.debug("Calling %s.%s with message=%r", domain, service, message)
        await self._hass.services.async_call(domain, service, {"message": message}, blocking=False)

    def _async_fire_state_changed(self) -> None:
        """Fire a HA event so entities refresh."""
        self._hass.bus.async_fire(f"{DOMAIN}_queue_updated")


def _parse_time(value: str | time) -> time:
    """Coerce a string like '09:00' or '09:00:00' to a :class:`datetime.time`."""
    if isinstance(value, time):
        return value
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: {value!r}")
