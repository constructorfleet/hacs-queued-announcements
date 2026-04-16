"""Config flow for Queued Announcements."""

from __future__ import annotations

from datetime import time
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ANNOUNCE_SERVICE,
    CONF_DEDUPE_MODE,
    CONF_FLUSH_TIME,
    CONF_SUMMARIZE_ON_FLUSH,
    CONF_TTL_MINUTES,
    CONF_WORK_HOURS_END,
    CONF_WORK_HOURS_START,
    DEDUPE_MODE_BOTH,
    DEDUPE_MODE_MESSAGE,
    DEDUPE_MODE_TAG,
    DEFAULT_DEDUPE_MODE,
    DEFAULT_SUMMARIZE_ON_FLUSH,
    DOMAIN,
)

DEDUPE_MODES = [DEDUPE_MODE_TAG, DEDUPE_MODE_MESSAGE, DEDUPE_MODE_BOTH]


def _time_str(t: Any) -> str:
    """Return a HH:MM:SS string from a time object or string."""
    if isinstance(t, time):
        return t.strftime("%H:%M:%S")
    return str(t)


class QueuedAnnouncementsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup via the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            # Basic validation – announce_service must contain a dot
            if "." not in user_input.get(CONF_ANNOUNCE_SERVICE, ""):
                errors[CONF_ANNOUNCE_SERVICE] = "invalid_service"
            else:
                return self.async_create_entry(
                    title="Queued Announcements",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_WORK_HOURS_START, default="09:00:00"): str,
                vol.Required(CONF_WORK_HOURS_END, default="17:00:00"): str,
                vol.Required(CONF_FLUSH_TIME, default="17:00:00"): str,
                vol.Required(CONF_ANNOUNCE_SERVICE): str,
                vol.Optional(CONF_DEDUPE_MODE, default=DEFAULT_DEDUPE_MODE): vol.In(DEDUPE_MODES),
                vol.Optional(CONF_TTL_MINUTES): vol.Any(None, vol.Coerce(int)),
                vol.Optional(CONF_SUMMARIZE_ON_FLUSH, default=DEFAULT_SUMMARIZE_ON_FLUSH): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> QueuedAnnouncementsOptionsFlow:
        return QueuedAnnouncementsOptionsFlow(config_entry)


class QueuedAnnouncementsOptionsFlow(config_entries.OptionsFlow):
    """Allow updating config without re-adding the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            if "." not in user_input.get(CONF_ANNOUNCE_SERVICE, ""):
                errors[CONF_ANNOUNCE_SERVICE] = "invalid_service"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WORK_HOURS_START,
                    default=current.get(CONF_WORK_HOURS_START, "09:00:00"),
                ): str,
                vol.Required(
                    CONF_WORK_HOURS_END,
                    default=current.get(CONF_WORK_HOURS_END, "17:00:00"),
                ): str,
                vol.Required(
                    CONF_FLUSH_TIME,
                    default=current.get(CONF_FLUSH_TIME, "17:00:00"),
                ): str,
                vol.Required(
                    CONF_ANNOUNCE_SERVICE,
                    default=current.get(CONF_ANNOUNCE_SERVICE, ""),
                ): str,
                vol.Optional(
                    CONF_DEDUPE_MODE,
                    default=current.get(CONF_DEDUPE_MODE, DEFAULT_DEDUPE_MODE),
                ): vol.In(DEDUPE_MODES),
                vol.Optional(
                    CONF_TTL_MINUTES,
                    default=current.get(CONF_TTL_MINUTES),
                ): vol.Any(None, vol.Coerce(int)),
                vol.Optional(
                    CONF_SUMMARIZE_ON_FLUSH,
                    default=current.get(CONF_SUMMARIZE_ON_FLUSH, DEFAULT_SUMMARIZE_ON_FLUSH),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
