"""Binary sensor – True when within configured work hours."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .manager import QueueManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager: QueueManager = hass.data[DOMAIN]
    async_add_entities([WorkHoursActiveSensor(manager, entry)], True)


class WorkHoursActiveSensor(BinarySensorEntity):
    """Binary sensor that is ON during configured work hours."""

    _attr_name = "Queued Announcements Work Hours Active"
    _attr_unique_id = "queued_announcements_work_hours_active"
    _attr_icon = "mdi:briefcase-clock-outline"

    def __init__(self, manager: QueueManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Queued Announcements",
            "manufacturer": "constructorfleet",
        }

    async def async_added_to_hass(self) -> None:
        """Refresh state every minute so the sensor stays accurate."""
        self.async_on_remove(async_track_time_change(self.hass, self._handle_tick, second=0))

    @callback
    def _handle_tick(self, _now: object) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self._manager.is_work_hours()
