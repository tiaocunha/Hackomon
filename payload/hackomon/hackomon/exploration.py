"""Discovery ledger, bounded rewards and a small offline upload queue."""

import csv
import datetime
import hashlib
import io
import math
import re

from . import __version__


MAC = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\Z")
MAX_QUEUE = 500
MAX_KNOWN = 10000
DAILY_XP_LIMIT = 120
COLUMNS = ("MAC", "SSID", "AuthMode", "FirstSeen", "Channel", "Frequency", "RSSI",
           "CurrentLatitude", "CurrentLongitude", "AltitudeMeters", "AccuracyMeters",
           "RCOIs", "MfgrId", "Type")


def normalize_observation(value):
    kind = str(value["type"]).upper()
    address = str(value["mac"]).upper()
    if kind not in ("WIFI", "BLE") or not MAC.fullmatch(address):
        raise ValueError("invalid discovery type/address")
    if (kind == "WIFI" and int(address[:2], 16) & 1
            or address in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF")):
        raise ValueError("invalid device address")
    lat, lon = float(value["lat"]), float(value["lon"])
    accuracy = float(value["accuracy"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 < accuracy <= 100):
        raise ValueError("invalid GPS fix")
    altitude = float(value.get("altitude", 0))
    if not math.isfinite(altitude):
        raise ValueError("invalid altitude")
    rssi = int(value["rssi"])
    if not -127 <= rssi <= 0:
        raise ValueError("invalid signal")
    timestamp = int(value["timestamp"])
    datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    clean = lambda text: "".join(c for c in str(text) if c.isprintable())[:128]
    return dict(type=kind, mac=address, name=clean(value.get("name", "")),
                auth=clean(value.get("auth", "[BLE]" if kind == "BLE" else "")),
                channel=max(0, min(233, int(value.get("channel", 0)))),
                frequency=max(0, min(7200, int(value.get("frequency", 0)))),
                rssi=rssi, lat=lat, lon=lon, altitude=altitude,
                accuracy=accuracy, timestamp=timestamp)


def record_observations(state, observations, now):
    day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date().isoformat()
    if state.exploration_day != day:
        state.exploration_day = day
        state.exploration_daily_xp = 0
    queued = {item["identity"] for item in state.network_queue}
    added = awarded = invalid = excluded = 0
    for raw in observations:
        try:
            item = normalize_observation(raw)
            if abs(item["timestamp"] - now) > 60:
                raise ValueError("stale observation")
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            invalid += 1
            continue
        if item["name"].lower().endswith(("_nomap", "_optout")):
            excluded += 1
            continue
        identity = hashlib.sha256((item["type"] + ":" + item["mac"]).encode()).hexdigest()
        previous_day = state.exploration_known.get(identity)
        if identity in queued or previous_day == day:
            continue
        if len(state.network_queue) >= MAX_QUEUE:
            break
        if previous_day is None and len(state.exploration_known) >= MAX_KNOWN:
            break
        reward = 0
        if previous_day is None:
            reward = min(2 if item["type"] == "WIFI" else 1,
                         max(0, DAILY_XP_LIMIT - state.exploration_daily_xp))
        state.exploration_known[identity] = day
        item["identity"] = identity
        state.network_queue.append(item)
        queued.add(identity)
        state.exploration_daily_xp += reward
        state.exploration_xp += reward
        state.exploration_counts[item["type"]] = state.exploration_counts.get(item["type"], 0) + 1
        awarded += reward
        added += 1
    state.xp += awarded
    state.level = min(99, 1 + state.xp // 30)
    return dict(added=added, xp=awarded, invalid=invalid, excluded=excluded,
                full=len(state.network_queue) >= MAX_QUEUE)


def export_csv(observations):
    """Explicit discovery fields only; never includes keys, pcaps or arbitrary input."""
    stream = io.StringIO(newline="")
    stream.write("WigleWifi-1.6,appRelease=%s,model=Hak5 Pager,device=hackomon,brand=Hackomon\n" % __version__)
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    for value in observations:
        item = normalize_observation(value)
        stamp = datetime.datetime.fromtimestamp(item["timestamp"], datetime.timezone.utc)
        writer.writerow((item["mac"], item["name"], item["auth"], stamp.strftime("%Y-%m-%d %H:%M:%S"),
                         item["channel"], item["frequency"], item["rssi"],
                         "%.7f" % item["lat"], "%.7f" % item["lon"],
                         item["altitude"], item["accuracy"], "", "0", item["type"]))
    return stream.getvalue().encode("utf-8")
