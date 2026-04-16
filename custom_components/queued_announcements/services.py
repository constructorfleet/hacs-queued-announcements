"""Service registration for Queued Announcements."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CRITICAL,
    ATTR_FORCE,
    ATTR_MESSAGE,
    ATTR_TAG,
    DEFAULT_TAG,
    DOMAIN,
    SERVICE_CLEAR,
    SERVICE_DEQUEUE,
    SERVICE_ENQUEUE,
    SERVICE_FLUSH,
    SERVICE_PEEK,
)
from .manager import QueueManager

_LOGGER = logging.getLogger(__name__)

ENQUEUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_TAG, default=DEFAULT_TAG): cv.string,
        vol.Optional(ATTR_CRITICAL, default=False): cv.boolean,
    }
)

DEQUEUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TAG): cv.string,
    }
)

FLUSH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)


def _get_manager(hass: HomeAssistant) -> QueueManager:
    return hass.data[DOMAIN]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register all Queued Announcements services."""

    async def handle_enqueue(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        await manager.async_enqueue(
            message=call.data[ATTR_MESSAGE],
            tag=call.data.get(ATTR_TAG, DEFAULT_TAG),
            critical=call.data.get(ATTR_CRITICAL, False),
        )

    async def handle_dequeue(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        await manager.async_dequeue(tag=call.data[ATTR_TAG])

    async def handle_flush(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        await manager.async_flush(force=call.data.get(ATTR_FORCE, False))

    async def handle_clear(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        await manager.async_clear()

    async def handle_peek(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        items = manager.async_peek()
        _LOGGER.info("Queue peek (%d item(s)): %s", len(items), items)

    hass.services.async_register(DOMAIN, SERVICE_ENQUEUE, handle_enqueue, schema=ENQUEUE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DEQUEUE, handle_dequeue, schema=DEQUEUE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_FLUSH, handle_flush, schema=FLUSH_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR, handle_clear)
    hass.services.async_register(DOMAIN, SERVICE_PEEK, handle_peek)

    _LOGGER.debug("Queued Announcements services registered")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove all Queued Announcements services."""
    for service in (SERVICE_ENQUEUE, SERVICE_DEQUEUE, SERVICE_FLUSH, SERVICE_CLEAR, SERVICE_PEEK):
        hass.services.async_remove(DOMAIN, service)
    _LOGGER.debug("Queued Announcements services removed")
