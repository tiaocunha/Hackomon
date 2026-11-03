"""Small offline field milestones and family voices, independent of radio control."""

RULES = (
    ("first_look", "Primeiro olhar", "discoveries", 10),
    ("two_worlds", "Dois mundos", "both", 5),
    ("explorer", "Passo explorador", "distance_m", 1000),
)
MEDAL_IDS = tuple(rule[0] for rule in RULES)

DISCOVERY_LINES = {
    "slime": "Uma descoberta brilhante!",
    "mammal": "Farejei uma novidade!",
    "avian": "Novidade no horizonte!",
    "reptile": "Mais uma pista no caminho!",
    "aquatic": "Nadamos ate outra pista!",
    "insect": "Antenas acharam novidade!",
    "spectral": "Senti uma presenca nova!",
    "botanical": "Nossa colecao floresceu!",
    "robotic": "Bip! Nova descoberta!",
    "cosmic": "Outro sinal no universo!",
}


def progress(summary):
    medals = summary.get("mission_medals", [])
    if (not isinstance(medals, list) or len(medals) > len(MEDAL_IDS)
            or any(not isinstance(value, str) or value not in MEDAL_IDS for value in medals)
            or len(set(medals)) != len(medals)):
        raise ValueError("invalid expedition medals")
    value = summary.get("mission_progress", {})
    if not isinstance(value, dict):
        raise ValueError("invalid mission progress")
    clean = {}
    for key in ("discoveries", "wifi", "ble"):
        count = value.get(key, 0)
        if type(count) is not int or not 0 <= count <= 10000:
            raise ValueError("invalid mission counter")
        clean[key] = count
    return clean


def cards(state, summary):
    values = progress(summary)
    values["both"] = min(values["wifi"], values["ble"])
    values["distance_m"] = max(0, int(summary.get("distance_m", 0)))
    return [dict(id=identity, title=title, value=min(target, values[key]), target=target,
                 earned=identity in state.field_badges,
                 detail="%d Wi-Fi + %d BLE novos" % (min(5, values["wifi"]), min(5, values["ble"]))
                        if key == "both" else "Metros com GPS" if key == "distance_m" else "Enderecos novos com XP")
            for identity, title, key, target in RULES]


def record(state, summary, reward=None):
    values = progress(summary)
    if reward:
        values["discoveries"] = min(10000, values["discoveries"] + reward["new"])
        for key, kind in (("wifi", "WIFI"), ("ble", "BLE")):
            values[key] = min(10000, values[key] + reward.get("new_by_type", {}).get(kind, 0))
    summary["mission_progress"] = values
    earned = []
    for card in cards(state, summary):
        if not card["earned"] and card["value"] >= card["target"]:
            state.field_badges.append(card["id"])
            medals = summary.setdefault("mission_medals", [])
            if card["id"] not in medals:
                medals.append(card["id"])
            earned.append(card["title"])
    # Medals never repay discovery XP or bypass evolution/care requirements.
    return earned


def speech(creature, event):
    if event == "discovery":
        return DISCOVERY_LINES.get(creature["family_id"], "Uma nova descoberta!")
    return {"mission": "Ganhamos uma medalha!", "gps_lost": "Sem GPS, sigo descobrindo.",
            "revisit": "Bom rever nossos caminhos!", "field": "Cada passeio nos aproxima!",
            "pause": "Uma pausa para respirar."}.get(event, "Vamos explorar juntos!")
