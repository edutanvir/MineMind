"""Simple usage limits so a public demo cannot burn the Gemini quota."""
import os
import threading
from datetime import datetime, timezone

SESSION_LIMIT = int(os.getenv("MINEMIND_SESSION_LIMIT", "15"))   # questions per browser session
DAILY_LIMIT = int(os.getenv("MINEMIND_DAILY_LIMIT", "300"))      # questions per server instance per UTC day

_lock = threading.Lock()
_day = None
_count = 0


def take_daily_slot() -> bool:
    """Reserve one question for today on this instance. False means the daily cap is reached."""
    global _day, _count
    today = datetime.now(timezone.utc).date()
    with _lock:
        if _day != today:
            _day, _count = today, 0
        if _count >= DAILY_LIMIT:
            return False
        _count += 1
        return True
