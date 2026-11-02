"""Target-scoped Bluetooth inventory. Service visibility is not a vulnerability."""

import json
import os
from pathlib import Path
import re
import time
import uuid

from .exploration import MAC
from .radio import command


DEVICE_KINDS = ("phone", "speaker", "headset", "mouse", "keyboard")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def target_scope(config, now=None, minimum_seconds=0):
    now = time.time() if now is None else now
    target = config.get("lab", {}).get("bluetooth", {})
    address = str(target.get("address", "")).upper()
    if (not MAC.fullmatch(address)
            or address in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF")):
        raise RuntimeError("Cadastre lab.bluetooth.address no config.json")
    # Bluetooth BD_ADDR is not an Ethernet multicast/unicast address.
    kind = target.get("kind", "")
    transport = target.get("transport", "auto")
    if kind not in DEVICE_KINDS or transport not in ("auto", "bredr", "le"):
        raise RuntimeError("Confira kind e transport do alvo Bluetooth")
    expires = int(target.get("authorized_until", 0))
    if not now < expires <= now + 86400 or expires - now < minimum_seconds:
        raise RuntimeError("Autorizacao Bluetooth ausente/expirada (max. 24h)")
    return address, kind, transport


def _clean(value):
    return "".join(char for char in value if char.isprintable())[:128]


def parse_info(text, address):
    """Only return metadata belonging to the requested BlueZ device block."""
    result = {"source": "bluez_cache", "available": False, "uuids": [], "flags": {}}
    active = False
    for raw in ANSI.sub("", text).splitlines():
        line = raw.strip()
        match = re.match(r"Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})(?:\s|$)", line)
        if match:
            active = match.group(1).upper() == address
            result["available"] |= active
            continue
        if not active:
            continue
        if line.startswith(("Name: ", "Alias: ", "AddressType: ", "Icon: ")):
            key, value = line.split(": ", 1)
            result[key.lower()] = _clean(value)
        elif line.startswith("UUID: "):
            identifier = re.search(r"\(([0-9a-fA-F-]{36})\)", line)
            if identifier and len(result["uuids"]) < 100:
                result["uuids"].append(identifier.group(1).lower())
        elif ": " in line:
            key, value = line.split(": ", 1)
            if key in ("Paired", "Bonded", "Trusted", "Connected", "ServicesResolved") and value in ("yes", "no"):
                result["flags"][key.lower()] = value == "yes"
    return result


def parse_sdp(text):
    records = []
    record = None
    for raw in ANSI.sub("", text).splitlines():
        line = raw.strip()
        if line.startswith("Service Name: "):
            if record is not None and record["name"]:
                records.append(record)
                record = None
            if record is None:
                record = dict(name="", channels=[])
            record["name"] = _clean(line.split(": ", 1)[1])
        elif line.startswith("Service RecHandle: "):
            if record is None:
                record = dict(name="", channels=[])
            value = line.split(": ", 1)[1]
            if re.fullmatch(r"0x[0-9a-fA-F]{1,8}", value):
                record["record_handle"] = value
        elif not line and record is not None:
            records.append(record)
            record = None
        elif record is not None and line.startswith("Channel: "):
            try:
                channel = int(line[9:])
                if 1 <= channel <= 30:
                    record["channels"].append(channel)
            except ValueError:
                pass
        if len(records) >= 100:
            break
    if record is not None and len(records) < 100:
        records.append(record)
    return [item for item in records if "record_handle" in item]


def audit(config, data_dir):
    address, kind, transport = target_scope(config, minimum_seconds=30)
    report = dict(address=address, device_kind=kind, transport=transport,
                  timestamp=int(time.time()), metadata={}, sdp={"status": "not_requested"},
                  verified_vulnerabilities=[],
                  not_tested=["pairing_pin", "authentication_bypass", "link_encryption",
                              "gatt_characteristic_access", "hid_input", "audio_access"],
                  limitations=["Cached flags describe the Pager relationship, not the device security policy.",
                               "Advertised UUIDs and SDP services do not prove unauthorized access."])
    try:
        text = command(["bluetoothctl", "--timeout", "5", "info", address], timeout=7)
        report["metadata"] = parse_info(text, address)
    except RuntimeError as error:
        report["metadata"] = {"available": False, "error": str(error)}
    if transport in ("auto", "bredr"):
        try:
            text = command(["sdptool", "browse", address], timeout=10)
            records = parse_sdp(text)
            report["sdp"] = dict(status="observed" if records else "inconclusive", records=records)
        except RuntimeError as error:
            report["sdp"] = dict(status="inconclusive", error=str(error), records=[])
    target_scope(config)
    observed = report["sdp"]["status"] == "observed"
    report["result"] = "services_observed" if observed else "metadata_only" if report["metadata"].get("available") else "inconclusive"
    root = Path(data_dir) / "lab"
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("bluetooth-" + uuid.uuid4().hex + ".json")
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return dict(completed=observed, reward_id="bluetooth:" + address,
                report_path=str(path),
                message=("Servicos SDP observados; relatorio local salvo" if observed
                         else "Auditoria inconclusiva/parcial; relatorio local salvo"))
