"""Constants for the Queued Announcements integration."""

DOMAIN = "queued_announcements"

STORAGE_KEY = f"{DOMAIN}_queue"
STORAGE_VERSION = 1

# Config entry fields
CONF_WORK_HOURS_START = "work_hours_start"
CONF_WORK_HOURS_END = "work_hours_end"
CONF_FLUSH_TIME = "flush_time"
CONF_ANNOUNCE_SERVICE = "announce_service"
CONF_DEDUPE_MODE = "dedupe_mode"
CONF_TTL_MINUTES = "ttl_minutes"
CONF_SUMMARIZE_ON_FLUSH = "summarize_on_flush"

# Dedupe modes
DEDUPE_MODE_TAG = "tag"
DEDUPE_MODE_MESSAGE = "message"
DEDUPE_MODE_BOTH = "both"

# Service names
SERVICE_ENQUEUE = "enqueue"
SERVICE_DEQUEUE = "dequeue"
SERVICE_FLUSH = "flush"
SERVICE_CLEAR = "clear"
SERVICE_PEEK = "peek"

# Service / event field names
ATTR_MESSAGE = "message"
ATTR_TAG = "tag"
ATTR_CRITICAL = "critical"
ATTR_FORCE = "force"

# Defaults
DEFAULT_TAG = "general"
DEFAULT_DEDUPE_MODE = DEDUPE_MODE_BOTH
DEFAULT_SUMMARIZE_ON_FLUSH = False
DEFAULT_TTL_MINUTES: int | None = None

# Platforms
PLATFORMS = ["sensor", "binary_sensor"]
