"""Finite active lives, successor eggs and explicit in-family branch choices."""

import math
import random

REVISION = 1
ADULT_LIFETIME = 10 * 60 * 60
VETERAN_AT = 8 * 60 * 60
EGG_PREPARATION = 60 * 60
EGG_INCUBATION = 20 * 60
MEMORIAL_LIMIT = 200
PROFILES = ("exploration", "sintonia", "companionship")
PROFILE_LABELS = dict(exploration="Exploracao", sintonia="Sintonia", companionship="Companheirismo")
LINE_PROFILES = ("exploration", "sintonia", "companionship", "exploration", "companionship")


def migrate(state):
    state.trainer_xp = state.xp
    state.trainer_level = state.level
    state.trainer_level_credit = state.level_credit
    state.birth_line_id = state.line_id
    state.hatched_lines = [state.line_id]
    state.pet_badges = list(state.field_badges)
    state.branch_locked = state.stage >= 2


def validate(state, catalog):
    if state.generations_revision != REVISION or type(state.generations_revision) is not int:
        raise ValueError("invalid generation revision")
    for key in ("trainer_xp", "trainer_level_credit", "generation", "memorial_total", "life_active_seconds",
                "adult_active_seconds", "pet_contacts", "egg_activity_seconds", "egg_incubation_seconds"):
        if type(getattr(state, key)) is not int or getattr(state, key) < 0:
            raise ValueError("invalid life counter")
    if state.generation < 1 or state.life_status not in ("alive", "memorial"):
        raise ValueError("invalid life status")
    if state.memorial_total != state.generation - (1 if state.life_status == "alive" else 0):
        raise ValueError("invalid generation count")
    if not 0 <= state.adult_active_seconds <= min(ADULT_LIFETIME, state.life_active_seconds):
        raise ValueError("invalid adult age")
    if not math.isfinite(state.pet_distance_m) or state.pet_distance_m < 0:
        raise ValueError("invalid lifetime distance")
    if state.birth_line_id not in catalog.line_by_id:
        raise ValueError("invalid birth line")
    for value, limit in ((state.hatched_lines, 50), (state.egg_offers, 3), (state.branch_offers, 3)):
        if (not isinstance(value, list) or len(value) > limit
                or any(not isinstance(key, str) or key not in catalog.line_by_id for key in value)
                or len(set(value)) != len(value)):
            raise ValueError("invalid line collection")
    if not isinstance(state.egg_line_id, str) or state.egg_line_id and state.egg_line_id not in state.egg_offers:
        raise ValueError("invalid selected egg")
    if state.egg_activity_seconds > EGG_PREPARATION or state.egg_incubation_seconds > EGG_INCUBATION:
        raise ValueError("invalid incubation progress")
    if state.egg_incubation_seconds and not state.egg_line_id:
        raise ValueError("missing incubating egg")
    if state.heritage_trait not in ("",) + PROFILES:
        raise ValueError("invalid heritage")
    if not isinstance(state.affinities, dict) or any(
            type(state.affinities.get(key, 0)) is not int or not 0 <= state.affinities.get(key, 0) <= 10000
            for key in PROFILES):
        raise ValueError("invalid affinity")
    if not isinstance(state.pet_badges, list) or any(
            not isinstance(key, str) or key not in state.field_badges for key in state.pet_badges) or len(set(state.pet_badges)) != len(state.pet_badges):
        raise ValueError("invalid pet medals")
    if type(state.branch_locked) is not bool or type(state.branch_pending) is not bool:
        raise ValueError("invalid branch state")
    if state.branch_pending and (state.stage != 1 or state.branch_locked or not state.branch_offers):
        raise ValueError("invalid pending evolution")
    family = catalog.evolution_line(state.line_id)["family_id"]
    if any(catalog.evolution_line(key)["family_id"] != family for key in state.branch_offers):
        raise ValueError("branch outside family")
    receipt = state.life_field_receipt
    if not isinstance(receipt, dict):
        raise ValueError("invalid life receipt")
    if receipt:
        import re
        if (not re.fullmatch(r"[0-9a-f]{32}", str(receipt.get("id", "")))
                or type(receipt.get("seconds")) is not int or receipt["seconds"] < 0
                or type(receipt.get("distance")) not in (int, float)
                or not math.isfinite(receipt["distance"]) or receipt["distance"] < 0):
            raise ValueError("invalid life receipt")
    if not isinstance(state.memorial, list) or len(state.memorial) > MEMORIAL_LIMIT:
        raise ValueError("invalid memorial")
    previous = 0
    for entry in state.memorial:
        if not isinstance(entry, dict) or entry.get("creature_id") not in catalog.creature_by_id:
            raise ValueError("invalid memorial creature")
        number = entry.get("generation")
        if type(number) is not int or not previous < number <= state.generation:
            raise ValueError("invalid memorial order")
        previous = number
        for key in ("xp", "level", "active_seconds", "contacts", "ended_at"):
            if type(entry.get(key)) is not int or entry[key] < 0:
                raise ValueError("invalid memorial counter")
        if (type(entry.get("distance_m")) not in (int, float) or not math.isfinite(entry["distance_m"])
                or entry["distance_m"] < 0 or entry.get("trait") not in PROFILES):
            raise ValueError("invalid memorial detail")
        if not isinstance(entry.get("medals"), list) or any(key not in state.field_badges for key in entry["medals"]):
            raise ValueError("invalid memorial medals")
    if state.life_status == "memorial" and (not state.memorial or state.memorial[-1]["generation"] != state.generation):
        raise ValueError("missing memorial entry")
    if state.life_status == "memorial" and state.adult_active_seconds != ADULT_LIFETIME:
        raise ValueError("invalid completed life")


def add_affinity(state, profile, amount):
    state.affinities[profile] = min(10000, state.affinities.get(profile, 0) + amount)


def affinity_score(state, profile):
    return state.affinities.get(profile, 0) + (2 if state.heritage_trait == profile else 0)


def primary_trait(state):
    return max(PROFILES, key=lambda key: affinity_score(state, key))


def age_label(state):
    if state.life_status == "memorial":
        return "Ciclo encerrado"
    return "Veterano" if state.adult_active_seconds >= VETERAN_AT else "Em jornada"


def record_contacts(state, reward):
    if state.life_status != "alive":
        return
    previous = state.pet_contacts
    state.pet_contacts += reward["new"] + reward["revisited"]
    add_affinity(state, "sintonia", state.pet_contacts // 10 - previous // 10)


def begin_field(state, summary):
    if state.life_field_receipt.get("id") != summary["id"]:
        state.life_field_receipt = dict(id=summary["id"], seconds=summary["field_progress"]["activity_seconds"],
                                       distance=float(summary.get("distance_m", 0)))


def observe_field(state, summary, now):
    """Consume persisted cumulative field counters; never age by wall-clock time."""
    value = summary["field_progress"]
    seconds, distance = value["activity_seconds"], float(summary.get("distance_m", 0))
    receipt = state.life_field_receipt
    if receipt.get("id") != summary["id"]:
        receipt = dict(id=summary["id"], seconds=0, distance=0.0)
        state.life_field_receipt = receipt
    elapsed = max(0, seconds - receipt["seconds"])
    traveled = max(0.0, distance - receipt["distance"])
    receipt["seconds"] = max(receipt["seconds"], seconds)
    receipt["distance"] = max(receipt["distance"], distance)
    state.egg_activity_seconds = min(EGG_PREPARATION, state.egg_activity_seconds + elapsed)
    if state.egg_line_id:
        state.egg_incubation_seconds = min(EGG_INCUBATION, state.egg_incubation_seconds + elapsed)
    if state.life_status != "alive":
        return dict(bond=0, event="")
    previous_age, previous_distance = state.life_active_seconds, state.pet_distance_m
    state.life_active_seconds += elapsed
    state.pet_distance_m += traveled
    bond = state.life_active_seconds // 600 - previous_age // 600
    state.field_bond += bond
    add_affinity(state, "companionship", bond)
    add_affinity(state, "exploration", int(state.pet_distance_m // 500) - int(previous_distance // 500))
    previous_adult = state.adult_active_seconds
    if state.stage >= 3:
        state.adult_active_seconds = min(ADULT_LIFETIME, previous_adult + elapsed)
    if state.adult_active_seconds >= ADULT_LIFETIME:
        state.life_status = "memorial"
        state.branch_pending = False
        state.branch_offers = []
        state.memorial_total += 1
        entry = dict(generation=state.generation, creature_id=state.creature_id, xp=state.xp,
                     level=state.level, active_seconds=state.life_active_seconds, contacts=state.pet_contacts,
                     distance_m=round(state.pet_distance_m, 2), medals=list(state.pet_badges),
                     ended_at=int(now), trait=primary_trait(state))
        state.memorial = (state.memorial + [entry])[-MEMORIAL_LIMIT:]
        return dict(bond=bond, event="ended")
    return dict(bond=bond, event="veteran" if previous_adult < VETERAN_AT <= state.adult_active_seconds else "")


def prepare_branch(state, catalog):
    if state.branch_offers:
        return
    family = catalog.evolution_line(state.line_id)["family_id"]
    others = [line for line in catalog.family_lines(family) if line["id"] != state.line_id]
    others.sort(key=lambda line: (-affinity_score(state, LINE_PROFILES[line["family_line_index"]]), line["family_line_index"]))
    state.branch_offers = [state.line_id] + [line["id"] for line in others[:2]]


def ensure_egg_offers(state, catalog, rng=None):
    if state.egg_activity_seconds < EGG_PREPARATION or state.egg_offers:
        return False
    missing = [line["id"] for line in catalog.lines if line["id"] not in state.hatched_lines]
    pool = missing or [line["id"] for line in catalog.lines]
    state.egg_offers = (rng or random.SystemRandom()).sample(pool, min(3, len(pool)))
    return True


def select_egg(state, line_id):
    if state.egg_activity_seconds < EGG_PREPARATION or state.egg_line_id or line_id not in state.egg_offers:
        raise ValueError("egg not available")
    state.egg_line_id = line_id
    state.egg_incubation_seconds = 0


def birth_ready(state):
    return state.life_status == "memorial" and bool(state.egg_line_id) and state.egg_incubation_seconds >= EGG_INCUBATION


def birth(state, catalog, now, summary=None):
    if not birth_ready(state):
        raise ValueError("successor not ready")
    line = state.egg_line_id
    first = catalog.creature_for_stage(line, 0)
    state.heritage_trait = state.memorial[-1]["trait"]
    state.generation += 1
    state.line_id = state.birth_line_id = line
    state.creature_id = first["id"]
    state.stage = 0
    state.xp = state.level_credit = state.care_points = state.field_bond = 0
    state.level = 1
    state.hunger, state.happiness, state.energy = 72, 68, 74
    state.born_at = state.last_seen_at = int(now)
    state.last_action_at = {}
    state.action_counts = dict(feed=0, play=0, rest=0)
    state.decay_remainders = dict(hunger=0, happiness=0, energy=0)
    state.life_status = "alive"
    state.life_active_seconds = state.adult_active_seconds = state.pet_contacts = 0
    state.pet_distance_m = 0.0
    state.pet_badges = []
    state.affinities = {}
    state.branch_locked = state.branch_pending = False
    state.branch_offers = []
    state.egg_line_id = ""
    state.egg_activity_seconds = state.egg_incubation_seconds = 0
    state.egg_offers = []
    if line not in state.hatched_lines:
        state.hatched_lines.append(line)
    if first["id"] not in state.discovered:
        state.discovered.append(first["id"])
    if summary is not None:
        summary["mission_progress"] = {}
        summary["mission_generation"] = state.generation
        progress = summary.get("field_progress", {})
        state.life_field_receipt = dict(id=summary["id"], seconds=progress.get("activity_seconds", 0),
                                       distance=float(summary.get("distance_m", 0)))
    else:
        state.life_field_receipt = {}
