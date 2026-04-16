"""Setup and teardown for the Queued Announcements integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_FLUSH_TIME, DOMAIN, PLATFORMS
from .manager import QueueManager, _parse_time
from .services import async_setup_services, async_unload_services
from .storage import QueueStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Queued Announcements from a config entry."""
    config = {**entry.data, **entry.options}

    storage = QueueStorage(hass)
    manager = QueueManager(hass, config, storage)
    await manager.async_load()

    hass.data[DOMAIN] = manager

    await async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule automatic flush
    flush_time_raw = config.get(CONF_FLUSH_TIME, "17:00:00")
    flush_time = _parse_time(flush_time_raw)

    async def _auto_flush(now: datetime) -> None:  # noqa: D401
        _LOGGER.debug("Scheduled flush triggered at %s", now)
        await manager.async_flush(force=False)

    entry.async_on_unload(
        async_track_time_change(
            hass,
            _auto_flush,
            hour=flush_time.hour,
            minute=flush_time.minute,
            second=0,
        )
    )

    # Reload when options are updated
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.debug("Queued Announcements integration set up")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down the integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_unload_services(hass)
        hass.data.pop(DOMAIN, None)
        _LOGGER.debug("Queued Announcements integration unloaded")
    return unload_ok
