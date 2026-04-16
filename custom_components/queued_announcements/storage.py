"""Persistence layer for the Queued Announcements integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class QueueStorage:
    """Wraps Home Assistant's Store for queue persistence."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )

    async def async_load(self) -> list[dict[str, Any]]:
        """Load queue from persistent storage."""
        data = await self._store.async_load()
        if data is None:
            _LOGGER.debug("No persisted queue found, starting fresh")
            return []
        _LOGGER.debug("Loaded %d item(s) from storage", len(data))
        return list(data)

    async def async_save(self, queue: list[dict[str, Any]]) -> None:
        """Persist current queue to storage."""
        await self._store.async_save(queue)
        _LOGGER.debug("Saved %d item(s) to storage", len(queue))

    async def async_clear(self) -> None:
        """Remove all persisted data."""
        await self._store.async_remove()
        _LOGGER.debug("Storage cleared")
