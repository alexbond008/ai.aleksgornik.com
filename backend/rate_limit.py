"""
Simple in-memory rate limiter. Resets daily per user (identified by JWT sub).
For production, swap the dict for Redis.
"""

from datetime import date
from typing import Dict, Tuple

FREE_DAILY_LIMIT = 10

# { user_id: (date_str, count) }
_store: Dict[str, Tuple[str, int]] = {}


def check_and_increment(user_id: str) -> Tuple[bool, int]:
    """
    Returns (allowed, remaining_after).
    Increments count if allowed.
    """
    today = date.today().isoformat()
    date_str, count = _store.get(user_id, (today, 0))

    if date_str != today:
        date_str, count = today, 0

    if count >= FREE_DAILY_LIMIT:
        return False, 0

    count += 1
    _store[user_id] = (date_str, count)
    return True, FREE_DAILY_LIMIT - count


def get_remaining(user_id: str) -> int:
    today = date.today().isoformat()
    date_str, count = _store.get(user_id, (today, 0))
    if date_str != today:
        return FREE_DAILY_LIMIT
    return max(0, FREE_DAILY_LIMIT - count)
