"""Local progression: growing level costs and resumable field activity rewards."""

import datetime
import math
import re
from . import generations

REVISION = 2
MAX_LEVEL = 100
REVISIT_SECONDS = 6 * 60 * 60
ACTIVITY_SECONDS = 600
ACTIVITY_XP = 10
DISTANCE_METERS = 500
DISTANCE_XP = 5


def threshold(level):
    steps = max(0, min(MAX_LEVEL - 1, int(level) - 1))
    return 40 * steps + 5 * steps * (steps - 1) // 2


def level_for(xp):
    low, high = 1, MAX_LEVEL
    while low < high:
        middle = (low + high + 1) // 2
        if threshold(middle) <= xp:
            low = middle
        else:
            high = middle - 1
    return low


def migrate_levels(state):
    """Retain earned level/proportional progress without changing recorded XP."""
    level = max(1, min(99, state.level))
    old_progress = min(29, max(0, state.xp - 30 * (level - 1)))
    needed = threshold(level + 1) - threshold(level)
    target = threshold(level) + old_progress * needed // 30
    state.level_credit = max(0, target - state.xp)
    state.level = level_for(state.xp + state.level_credit)
    state.progression_revision = REVISION


def level_progress(state):
    if state.level >= MAX_LEVEL:
        return 0, 0
    needed = threshold(state.level + 1) - threshold(state.level)
    current = max(0, min(needed, state.xp + state.level_credit - threshold(state.level)))
    return current, needed


def grant(state, amount, now=None, exploration=False):
    if type(amount) is not int or amount < 0:
        raise ValueError("invalid XP award")
    if exploration:
        day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date().isoformat()
        if state.exploration_day != day:
            state.exploration_day = day
            state.exploration_daily_xp = 0
        state.exploration_xp += amount
        state.exploration_daily_xp += amount
    state.trainer_xp += amount
    state.trainer_level = level_for(state.trainer_xp + state.trainer_level_credit)
    if state.life_status == "alive":
        state.xp += amount
        state.level = level_for(state.xp + state.level_credit)


def field_progress(summary):
    if type(summary.get("revisit_awards", 0)) is not int or summary.get("revisit_awards", 0) < 0:
        raise ValueError("invalid revisit counter")
    breakdown = summary.get("xp_breakdown", {})
    if not isinstance(breakdown, dict) or any(
            type(breakdown.get(key, 0)) is not int or breakdown.get(key, 0) < 0
            for key in ("discoveries", "revisits", "activity", "distance")):
        raise ValueError("invalid XP breakdown")
    value = summary.get("field_progress")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("invalid field progress")
    for key in ("activity_seconds", "distance_baseline"):
        if type(value.get(key)) is not int or value[key] < 0:
            raise ValueError("invalid field counter")
    stamp = value.get("last_activity_at")
    if stamp is not None and (type(stamp) is not int or stamp < 0):
        raise ValueError("invalid activity time")
    return value


def reset_activity(summary):
    value = field_progress(summary)
    if value is None:
        value = dict(activity_seconds=0, distance_baseline=int(summary.get("distance_m", 0) // DISTANCE_METERS),
                     last_activity_at=None)
        summary["field_progress"] = value
    value["last_activity_at"] = None


def field_rewards(state, summary, now, observed=None):
    """Pay distance/time blocks once in the same atomic save as XP and bond."""
    now = int(now)
    value = field_progress(summary)
    if value is None:
        reset_activity(summary)
        value = summary["field_progress"]
    if summary.get("status") != "running":
        value["last_activity_at"] = None
        return dict(xp=0, activity_xp=0, distance_xp=0, bond=0)
    if observed is not None:
        previous = value["last_activity_at"]
        if observed and previous is not None and 0 < now - previous <= 45:
            value["activity_seconds"] += now - previous
        value["last_activity_at"] = now if observed else None
    identity = summary["id"]
    if not re.fullmatch(r"[0-9a-f]{32}", identity):
        raise ValueError("invalid field session")
    receipt = state.field_bonus_receipt
    if receipt.get("id") != identity:
        receipt = dict(id=identity, activity=0, distance=0)
        state.field_bonus_receipt = receipt
    meters = float(summary.get("distance_m", 0))
    if not math.isfinite(meters) or meters < 0:
        raise ValueError("invalid rewarded distance")
    activity = value["activity_seconds"] // ACTIVITY_SECONDS
    distance = max(0, int(meters // DISTANCE_METERS) - value["distance_baseline"])
    new_activity = max(0, activity - receipt["activity"])
    new_distance = max(0, distance - receipt["distance"])
    receipt["activity"] = max(receipt["activity"], activity)
    receipt["distance"] = max(receipt["distance"], distance)
    amount = new_activity * ACTIVITY_XP + new_distance * DISTANCE_XP
    grant(state, amount, now=now, exploration=True)
    life = generations.observe_field(state, summary, now)
    return dict(xp=amount, activity_xp=new_activity * ACTIVITY_XP,
                distance_xp=new_distance * DISTANCE_XP, bond=life["bond"], life_event=life["event"])
