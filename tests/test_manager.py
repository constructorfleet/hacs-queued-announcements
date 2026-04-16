"""Unit tests for the QueueManager core logic."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Allow imports from the integration without a full HA install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from custom_components.queued_announcements.const import (
    CONF_ANNOUNCE_SERVICE,
    CONF_DEDUPE_MODE,
    CONF_TTL_MINUTES,
    CONF_WORK_HOURS_END,
    CONF_WORK_HOURS_START,
    DEDUPE_MODE_BOTH,
    DEDUPE_MODE_MESSAGE,
    DEDUPE_MODE_TAG,
)
from custom_components.queued_announcements.manager import QueueItem, QueueManager, _parse_time
from custom_components.queued_announcements.storage import QueueStorage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(
    hass,
    *,
    work_start: str = "09:00:00",
    work_end: str = "17:00:00",
    announce_service: str = "notify.test",
    dedupe_mode: str = DEDUPE_MODE_BOTH,
    ttl_minutes: int | None = None,
    queue_data: list | None = None,
) -> QueueManager:
    storage = AsyncMock(spec=QueueStorage)
    storage.async_load.return_value = queue_data or []
    storage.async_save = AsyncMock()
    config = {
        CONF_WORK_HOURS_START: work_start,
        CONF_WORK_HOURS_END: work_end,
        CONF_ANNOUNCE_SERVICE: announce_service,
        CONF_DEDUPE_MODE: dedupe_mode,
        CONF_TTL_MINUTES: ttl_minutes,
    }
    return QueueManager(hass, config, storage)


def _make_hass() -> MagicMock:
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


# ---------------------------------------------------------------------------
# _parse_time
# ---------------------------------------------------------------------------


class TestParseTime:
    def test_hhmm(self):
        assert _parse_time("09:00") == time(9, 0)

    def test_hhmmss(self):
        assert _parse_time("17:30:00") == time(17, 30, 0)

    def test_time_passthrough(self):
        t = time(8, 0)
        assert _parse_time(t) is t

    def test_invalid(self):
        with pytest.raises(ValueError):
            _parse_time("not-a-time")


# ---------------------------------------------------------------------------
# QueueItem
# ---------------------------------------------------------------------------


class TestQueueItem:
    def test_create_roundtrip(self):
        item = QueueItem.create("hello", "test", False)
        assert item.message == "hello"
        assert item.tag == "test"
        assert item.critical is False
        d = item.as_dict()
        restored = QueueItem.from_dict(d)
        assert restored.id == item.id
        assert restored.message == item.message

    def test_is_expired_no_ttl(self):
        item = QueueItem.create("msg", "tag", False)
        assert item.is_expired(None) is False

    def test_is_expired_within_ttl(self):
        item = QueueItem.create("msg", "tag", False)
        assert item.is_expired(60) is False

    def test_is_expired_past_ttl(self):
        past = datetime(2000, 1, 1, tzinfo=UTC)
        item = QueueItem(
            id="x",
            message="old",
            tag="t",
            created_at=past.isoformat(),
            critical=False,
        )
        assert item.is_expired(1) is True


# ---------------------------------------------------------------------------
# QueueManager – is_work_hours
# ---------------------------------------------------------------------------


class TestIsWorkHours:
    def test_within_work_hours(self):
        hass = _make_hass()
        mgr = _make_manager(hass, work_start="08:00:00", work_end="18:00:00")
        fake_now = MagicMock()
        fake_now.time.return_value = time(12, 0)
        with patch(
            "custom_components.queued_announcements.manager.datetime",
            wraps=datetime,
        ) as mock_dt:
            mock_dt.now.return_value = fake_now
            assert mgr.is_work_hours() is True

    def test_outside_work_hours(self):
        hass = _make_hass()
        mgr = _make_manager(hass, work_start="09:00:00", work_end="17:00:00")
        fake_now = MagicMock()
        fake_now.time.return_value = time(20, 0)
        with patch(
            "custom_components.queued_announcements.manager.datetime",
            wraps=datetime,
        ) as mock_dt:
            mock_dt.now.return_value = fake_now
            assert mgr.is_work_hours() is False


# ---------------------------------------------------------------------------
# QueueManager – enqueue
# ---------------------------------------------------------------------------


class TestEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_during_work_hours(self):
        hass = _make_hass()
        mgr = _make_manager(hass, work_start="08:00:00", work_end="18:00:00")
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("hello", tag="greet")
        assert mgr.queue_count == 1
        assert mgr.queue[0].message == "hello"

    @pytest.mark.asyncio
    async def test_immediate_outside_work_hours(self):
        hass = _make_hass()
        mgr = _make_manager(hass, work_start="09:00:00", work_end="10:00:00")
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=False):
            await mgr.async_enqueue("off-hours msg")
        assert mgr.queue_count == 0
        hass.services.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_critical_bypasses_queue(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("urgent!", critical=True)
        assert mgr.queue_count == 0
        hass.services.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dedupe_tag(self):
        hass = _make_hass()
        mgr = _make_manager(hass, dedupe_mode=DEDUPE_MODE_TAG)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("first", tag="dup")
            await mgr.async_enqueue("second", tag="dup")
        assert mgr.queue_count == 1

    @pytest.mark.asyncio
    async def test_dedupe_message(self):
        hass = _make_hass()
        mgr = _make_manager(hass, dedupe_mode=DEDUPE_MODE_MESSAGE)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("same msg", tag="a")
            await mgr.async_enqueue("same msg", tag="b")
        assert mgr.queue_count == 1

    @pytest.mark.asyncio
    async def test_dedupe_both_allows_different(self):
        hass = _make_hass()
        mgr = _make_manager(hass, dedupe_mode=DEDUPE_MODE_BOTH)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("msg A", tag="a")
            await mgr.async_enqueue("msg B", tag="b")
        assert mgr.queue_count == 2


# ---------------------------------------------------------------------------
# QueueManager – dequeue
# ---------------------------------------------------------------------------


class TestDequeue:
    @pytest.mark.asyncio
    async def test_dequeue_removes_matching_tag(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("keep me", tag="other")
            await mgr.async_enqueue("remove me", tag="gone")
        removed = await mgr.async_dequeue("gone")
        assert removed == 1
        assert mgr.queue_count == 1
        assert mgr.queue[0].tag == "other"

    @pytest.mark.asyncio
    async def test_dequeue_nonexistent_tag(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        removed = await mgr.async_dequeue("ghost")
        assert removed == 0


# ---------------------------------------------------------------------------
# QueueManager – flush
# ---------------------------------------------------------------------------


class TestFlush:
    @pytest.mark.asyncio
    async def test_flush_during_work_hours_noop(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("queued", tag="t")
            await mgr.async_flush(force=False)
        assert mgr.queue_count == 1
        hass.services.async_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_flush_forced_during_work_hours(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("queued")
            await mgr.async_flush(force=True)
        assert mgr.queue_count == 0
        hass.services.async_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_flush_drops_expired_items(self):
        hass = _make_hass()
        past = datetime(2000, 1, 1, tzinfo=UTC).isoformat()
        old_item = {
            "id": "old-1",
            "message": "stale",
            "tag": "t",
            "created_at": past,
            "critical": False,
        }
        mgr = _make_manager(hass, ttl_minutes=1, queue_data=[old_item])
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=False):
            await mgr.async_flush()
        assert mgr.queue_count == 0
        hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# QueueManager – clear
# ---------------------------------------------------------------------------


class TestClear:
    @pytest.mark.asyncio
    async def test_clear_empties_queue(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("one")
            await mgr.async_enqueue("two", tag="b")
        await mgr.async_clear()
        assert mgr.queue_count == 0
        hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# QueueManager – peek
# ---------------------------------------------------------------------------


class TestPeek:
    @pytest.mark.asyncio
    async def test_peek_returns_snapshot(self):
        hass = _make_hass()
        mgr = _make_manager(hass)
        await mgr.async_load()
        with patch.object(mgr, "is_work_hours", return_value=True):
            await mgr.async_enqueue("peek me")
        items = mgr.async_peek()
        assert len(items) == 1
        assert items[0]["message"] == "peek me"
        # Mutating snapshot does not affect internal queue
        items.clear()
        assert mgr.queue_count == 1
