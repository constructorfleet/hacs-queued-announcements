"""Sensor platform for Queued Announcements – exposes queue count."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .manager import QueueManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager: QueueManager = hass.data[DOMAIN]
    async_add_entities([QueuedAnnouncementsCountSensor(manager, entry)], True)


class QueuedAnnouncementsCountSensor(SensorEntity):
    """Reports the number of items currently in the announcement queue."""

    _attr_name = "Queued Announcements Count"
    _attr_unique_id = "queued_announcements_count"
    _attr_icon = "mdi:bullhorn-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "announcements"

    def __init__(self, manager: QueueManager, entry: ConfigEntry) -> None:
        self._manager = manager
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Queued Announcements",
            "manufacturer": "constructorfleet",
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to queue update events."""
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_queue_updated", self._handle_update)
        )

    @callback
    def _handle_update(self, _event: object) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        return self._manager.queue_count
