"""Discover, select and assess a client AP without a pre-registered address."""

import json
from contextlib import contextmanager
import os
from pathlib import Path
import re
import time
import uuid

from . import lab, radio
from .exploration import MAC


def interfaces(text):
    found = []
    current = None
    phy = ""
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"phy#\d+", line):
            phy = "phy" + line[4:]
            current = None
        elif line.startswith("Interface "):
            name = line.split()[1]
            current = None
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", name):
                current = dict(name=name, type="", frequency=0, phy=phy)
                found.append(current)
        elif line.startswith("Unnamed/non-netdev interface"):
            current = dict(name="", type="unknown", frequency=0, phy=phy)
            found.append(current)
        elif current is not None and line.startswith("type "):
            current["type"] = line[5:]
        elif current is not None and line.startswith("channel "):
            match = re.search(r"\((\d+) MHz\)", line)
            if match:
                current["frequency"] = int(match.group(1))
    return found


@contextmanager
def monitor_for(frequency, cleanup):
    choices = interfaces(radio.command(["iw", "dev"], timeout=3))
    matching = next((item["name"] for item in choices
                     if item["type"] == "monitor" and item["frequency"] == frequency), "")
    if matching:
        cleanup["status"] = "existing_interface_unchanged"
        yield matching
        return
    candidate = None
    # Only use an idle PHY with exactly one managed interface. APs, other monitor
    # interfaces and unaccounted netdevs make the PHY ineligible for auto-tuning.
    for item in [value for value in choices if value["type"] == "managed"][:3]:
        if not item["phy"] or sum(value["phy"] == item["phy"] for value in choices) != 1:
            continue
        link = radio.command(["iw", "dev", item["name"], "link"], timeout=3)
        if "Not connected." in link:
            candidate = item
            break
    if candidate is None:
        raise RuntimeError("Sem radio livre/monitor no canal; captura nao executada")
    name = "hkm" + uuid.uuid4().hex[:8]
    created = False
    try:
        radio.command(["iw", "phy", candidate["phy"], "interface", "add", name, "type", "monitor"], timeout=3)
        created = True
        cleanup.update(status="pending", interface=name)
        radio.command(["ip", "link", "set", "dev", name, "up"], timeout=3)
        radio.command(["iw", "dev", name, "set", "freq", str(frequency)], timeout=3)
        yield name
    finally:
        if created:
            try:
                radio.command(["iw", "dev", name, "del"], timeout=3)
                cleanup["status"] = "temporary_interface_removed"
            except RuntimeError:
                cleanup["status"] = "removal_failed"
                cleanup["note"] = "Interface temporaria requer remocao: " + name


def find_networks(config):
    interface = str(config.get("wifi_interface", ""))
    if interface:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", interface):
            raise RuntimeError("Interface Wi-Fi invalida")
    else:
        available = interfaces(radio.command(["iw", "dev"], timeout=3))
        interface = ""
        for item in [value for value in available if value["type"] == "managed"][:3]:
            status = radio.command(["iw", "dev", item["name"], "link"], timeout=3)
            if "Not connected." in status:
                interface = item["name"]
                break
        if not interface:
            raise RuntimeError("Sem interface livre; escolha wifi_interface uma vez")
    # Client assessment is local: GPS and map upload are not involved.
    text = radio.command(["iw", "dev", interface, "scan", "passive"], timeout=20)
    values = radio.wifi_observations(text, int(time.time()))
    unique = {item["mac"]: item for item in values
              if not int(item["mac"][:2], 16) & 1 and item["mac"] != "00:00:00:00:00:00"}
    return sorted(unique.values(), key=lambda item: item["rssi"], reverse=True)[:100]


def session_config(config, target, now=None):
    now = int(time.time() if now is None else now)
    address = str(target.get("mac", "")).upper()
    if (not MAC.fullmatch(address) or int(address[:2], 16) & 1
            or address == "00:00:00:00:00:00"):
        raise RuntimeError("Selecione uma rede valida na lista")
    if not 0 <= now - int(target.get("timestamp", 0)) <= 300:
        raise RuntimeError("Busca antiga; atualize as redes do atendimento")
    if int(target.get("frequency", 0)) <= 0:
        raise RuntimeError("Busca sem frequencia; atualize as redes")
    # Do not mutate/write the static config or inherit its previous target.
    session = dict(config)
    session["lab"] = dict(bssid=address, authorized_until=now + 3600,
                          monitor_interface="")
    return session


def posture(target):
    security = target.get("security", {})
    findings = []
    def add(identifier, priority, observation, recommendation):
        findings.append(dict(id=identifier, priority=priority, evidence=observation,
                             recommendation=recommendation, confirmed_exploit=False))
    if target["auth"] == "[OPEN]":
        add("open", "review", "Rede anuncia acesso aberto; portal cativo nao foi avaliado.",
            "Verificar se o acesso aberto e intencional e avaliar isolamento/criptografia.")
    if security.get("wpa"):
        add("wpa1", "review", "Compatibilidade WPA legado anunciada.",
            "Avaliar remover compatibilidade WPA legado.")
    if "TKIP" in security.get("ciphers", []):
        add("tkip", "review", "Cifra TKIP anunciada.", "Avaliar usar somente cifras modernas compativeis.")
    if security.get("wps"):
        add("wps", "info", "WPS anunciado; PIN e bloqueio nao foram testados.",
            "Confirmar necessidade do WPS e revisar configuracao no roteador.")
    if security.get("pmf") in ("optional", "not_advertised"):
        add("pmf", "info", "Protecao de quadros de gerenciamento nao anunciada como obrigatoria.",
            "Avaliar exigir PMF conforme compatibilidade dos clientes.")
    if target["auth"] in ("[UNKNOWN]", "[LEGACY/UNKNOWN]"):
        add("unknown", "inconclusive", "Anuncio insuficiente para classificar a seguranca.",
            "Confirmar configuracao no roteador; nao assumir WEP ou rede segura.")
    return findings


def assess(config, target, data_dir):
    session = session_config(config, target)
    address = session["lab"]["bssid"]
    report = dict(session_id=uuid.uuid4().hex, timestamp=int(time.time()),
                  target={key: target.get(key) for key in (
                      "mac", "name", "auth", "frequency", "rssi", "security")},
                  scope="selected_bssid_only", findings=posture(target),
                  capture={"status": "not_run"}, dictionary={"status": "not_run"},
                  cleanup={"status": "not_needed"},
                  not_tested=["router_admin", "firmware_cves", "client_isolation", "lan_services",
                              "segmentation", "wps_pin", "wpa3_sae", "forced_reconnection"],
                  summary="Anuncios avaliados; ausencia de achados nao comprova seguranca.")
    try:
        if target["auth"] not in ("[WPA]", "[WPA2]", "[WPA2+WPA3]"):
            raise RuntimeError("Captura WPA/WPA2 nao aplicavel ao modo anunciado")
        with monitor_for(target["frequency"], report["cleanup"]) as monitor:
            session["lab"]["monitor_interface"] = monitor
            captured = lab.capture(session, data_dir)
            report["capture"] = dict(status="eapol_observed", path=captured["path"],
                                     note="Completude do handshake ainda nao comprovada")
        dictionary = Path(data_dir) / "lab" / "dictionary.txt"
        if "PSK" not in target.get("security", {}).get("akm", []):
            report["dictionary"] = dict(status="not_run", note="PSK nao confirmado no anuncio")
        elif dictionary.is_file():
            result = lab.test_dictionary(session, data_dir)
            report["dictionary"] = dict(status="key_recovered" if result["found"] else "inconclusive",
                                         note=result["message"])
        else:
            report["dictionary"] = dict(status="not_run", note="Dicionario local nao instalado")
    except RuntimeError as error:
        key = "dictionary" if report["capture"]["status"] == "eapol_observed" else "capture"
        report[key] = dict(status="inconclusive", note=str(error))
    root = Path(data_dir) / "visits"
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("visit-" + report["session_id"] + ".json")
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    readable = path.with_suffix(".txt")
    clean_name = "".join(char for char in str(target.get("name", "")) if char.isprintable())[:128]
    lines = ["HACKOMON - RELATORIO DE ATENDIMENTO", "",
             "Rede: " + (clean_name or "SSID oculto"), "BSSID: " + address,
             "Autenticacao anunciada: " + target["auth"],
             "Escopo: somente o BSSID selecionado nesta sessao.", "", report["summary"], ""]
    for finding in report["findings"]:
        lines.extend(["Observacao: " + finding["evidence"],
                      "Recomendacao: " + finding["recommendation"], ""])
    for operation in ("capture", "dictionary"):
        entry = report[operation]
        lines.append(operation + ": " + entry["status"] + " - " + entry.get("note", ""))
    lines.extend(["", "Nao testado: " + ", ".join(report["not_tested"]),
                  "Limpeza do radio: " + report["cleanup"]["status"],
                  report["cleanup"].get("note", ""),
                  "Relatorio e evidencias locais; nenhum envio ao mapa."])
    descriptor = os.open(str(readable), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    message = "Atendimento salvo: %d observacoes; veja o relatorio" % len(report["findings"])
    if report["cleanup"]["status"] == "removal_failed":
        message = "ATENCAO: interface temporaria nao removida; veja relatorio"
    return dict(message=message,
                report_path=str(path), text_path=str(readable), completed=True, reward_id="visit:" + address,
                report=report)
