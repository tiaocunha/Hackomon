"""Serializable game state and care actions."""

import random
import hashlib
import re
import time
from dataclasses import asdict, dataclass, field

from .constants import STATE_SCHEMA_VERSION
from .exploration import MAX_KNOWN, MAX_QUEUE, normalize_observation
from .missions import MEDAL_IDS
from . import generations, progression


ACTION_RULES = {
    "feed": {
        "cooldown": 12,
        "xp": 12,
        "care": 1,
        "delta": {"hunger": 24, "happiness": 2, "energy": -1},
    },
    "play": {
        "cooldown": 12,
        "xp": 15,
        "care": 2,
        "delta": {"hunger": -4, "happiness": 18, "energy": -8},
    },
    "rest": {
        "cooldown": 12,
        "xp": 8,
        "care": 1,
        "delta": {"hunger": -3, "happiness": 1, "energy": 26},
    },
}


@dataclass
class ActionOutcome:
    accepted: bool
    message: str
    action: str


@dataclass
class GameState:
    schema_version: int
    line_id: str
    creature_id: str
    stage: int
    level: int = 1
    xp: int = 0
    care_points: int = 0
    hunger: int = 72
    happiness: int = 68
    energy: int = 74
    born_at: int = 0
    last_seen_at: int = 0
    last_action_at: dict = field(default_factory=dict)
    decay_remainders: dict = field(
        default_factory=lambda: {"hunger": 0, "happiness": 0, "energy": 0}
    )
    discovered: list = field(default_factory=list)
    action_counts: dict = field(default_factory=lambda: {"feed": 0, "play": 0, "rest": 0})
    exploration_known: dict = field(default_factory=dict)
    discovery_rewarded: dict = field(default_factory=dict)
    exploration_day: str = ""
    exploration_daily_xp: int = 0
    exploration_xp: int = 0
    exploration_counts: dict = field(default_factory=lambda: {"WIFI": 0, "BLE": 0})
    network_queue: list = field(default_factory=list)
    lab_rewards: list = field(default_factory=list)
    field_badges: list = field(default_factory=list)
    progression_revision: int = progression.REVISION
    level_credit: int = 0
    field_bond: int = 0
    revisit_rewarded_at: dict = field(default_factory=dict)
    field_bonus_receipt: dict = field(default_factory=dict)
    generations_revision: int = generations.REVISION
    trainer_xp: int = 0
    trainer_level: int = 1
    trainer_level_credit: int = 0
    generation: int = 1
    life_status: str = "alive"
    life_active_seconds: int = 0
    adult_active_seconds: int = 0
    pet_contacts: int = 0
    pet_distance_m: float = 0.0
    life_field_receipt: dict = field(default_factory=dict)
    birth_line_id: str = ""
    hatched_lines: list = field(default_factory=list)
    pet_badges: list = field(default_factory=list)
    affinities: dict = field(default_factory=dict)
    heritage_trait: str = ""
    branch_locked: bool = False
    branch_pending: bool = False
    branch_offers: list = field(default_factory=list)
    egg_activity_seconds: int = 0
    egg_incubation_seconds: int = 0
    egg_offers: list = field(default_factory=list)
    egg_line_id: str = ""
    memorial_total: int = 0
    memorial: list = field(default_factory=list)

    @classmethod
    def new(cls, catalog, line_id=None, now=None, rng=None):
        now = int(time.time() if now is None else now)
        if line_id is None:
            chooser = rng or random.SystemRandom()
            line_id = chooser.choice(catalog.lines)["id"]
        first = catalog.creature_for_stage(line_id, 0)
        return cls(
            schema_version=STATE_SCHEMA_VERSION,
            line_id=line_id,
            creature_id=first["id"],
            stage=0,
            born_at=now,
            last_seen_at=now,
            discovered=[first["id"]],
            birth_line_id=line_id,
            hatched_lines=[line_id],
        )

    @classmethod
    def from_dict(cls, value, catalog):
        if value.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ValueError("unsupported state schema")
        line_id = value.get("line_id")
        creature_id = value.get("creature_id")
        stage = int(value.get("stage", -1))
        expected = catalog.creature_for_stage(line_id, stage)
        if expected["id"] != creature_id:
            raise ValueError("saved creature does not match its line and stage")

        known_fields = {field_info.name for field_info in cls.__dataclass_fields__.values()}
        clean = {key: item for key, item in value.items() if key in known_fields}
        state = cls(**clean)
        if (type(state.progression_revision) is not int or state.progression_revision != progression.REVISION
                or type(state.level_credit) is not int or state.level_credit < 0
                or type(state.field_bond) is not int or state.field_bond < 0
                or not isinstance(state.revisit_rewarded_at, dict) or len(state.revisit_rewarded_at) > MAX_KNOWN):
            raise ValueError("invalid progression state")
        for identity, stamp in state.revisit_rewarded_at.items():
            if (not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity)
                    or type(stamp) is not int or stamp < 0):
                raise ValueError("invalid revisit receipt")
        receipt = state.field_bonus_receipt
        if not isinstance(receipt, dict):
            raise ValueError("invalid field receipt")
        if receipt and (not re.fullmatch(r"[0-9a-f]{32}", str(receipt.get("id", "")))
                        or any(type(receipt.get(key)) is not int or receipt[key] < 0 for key in ("activity", "distance"))):
            raise ValueError("invalid field receipt")
        if (not isinstance(state.field_badges, list) or len(state.field_badges) > len(MEDAL_IDS)
                or any(not isinstance(value, str) or value not in MEDAL_IDS for value in state.field_badges)
                or len(set(state.field_badges)) != len(state.field_badges)):
            raise ValueError("invalid field medals")
        if "discovery_rewarded" not in value and isinstance(state.exploration_known, dict):
            state.discovery_rewarded = dict(state.exploration_known)
        if (not isinstance(state.exploration_known, dict)
                or len(state.exploration_known) > MAX_KNOWN
                or not isinstance(state.discovery_rewarded, dict)
                or len(state.discovery_rewarded) > MAX_KNOWN
                or not isinstance(state.network_queue, list)
                or len(state.network_queue) > MAX_QUEUE
                or not isinstance(state.exploration_counts, dict)
                or not isinstance(state.lab_rewards, list)
                or len(state.lab_rewards) > MAX_KNOWN):
            raise ValueError("invalid discovery ledger")
        for identity, day in list(state.exploration_known.items()) + list(state.discovery_rewarded.items()):
            if (not re.fullmatch(r"[0-9a-f]{64}", identity)
                    or not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
                raise ValueError("invalid discovery identity")
        for item in state.network_queue:
            observation = normalize_observation(item)
            identity = hashlib.sha256((observation["type"] + ":" + observation["mac"]).encode()).hexdigest()
            if item.get("identity") != identity:
                raise ValueError("invalid queued discovery")
        state.exploration_daily_xp = max(0, int(state.exploration_daily_xp))
        state.exploration_xp = max(0, int(state.exploration_xp))
        state._clamp_stats()
        if "progression_revision" not in value:
            progression.migrate_levels(state)
        else:
            state.level = progression.level_for(state.xp + state.level_credit)
        if "generations_revision" not in value:
            generations.migrate(state)
        generations.validate(state, catalog)
        state.trainer_level = progression.level_for(state.trainer_xp + state.trainer_level_credit)
        state.discovered = [item for item in state.discovered if item in catalog.creature_by_id]
        if creature_id not in state.discovered:
            state.discovered.append(creature_id)
        for action in ACTION_RULES:
            state.action_counts.setdefault(action, 0)
        for stat in ("hunger", "happiness", "energy"):
            state.decay_remainders.setdefault(stat, 0)
        return state

    def to_dict(self):
        return asdict(self)

    @property
    def wellness(self):
        return (self.hunger + self.happiness + self.energy) // 3

    def _clamp_stats(self):
        self.hunger = max(0, min(100, int(self.hunger)))
        self.happiness = max(0, min(100, int(self.happiness)))
        self.energy = max(0, min(100, int(self.energy)))
        self.level = max(1, min(progression.MAX_LEVEL, int(self.level)))
        self.xp = max(0, int(self.xp))
        self.care_points = max(0, int(self.care_points))

    def apply_elapsed_time(self, now=None):
        now = int(time.time() if now is None else now)
        if self.life_status != "alive":
            self.last_seen_at = now
            return False
        elapsed = max(0, min(now - int(self.last_seen_at), 48 * 60 * 60))
        if elapsed == 0:
            self.last_seen_at = now
            return False

        changed = False
        periods = {"hunger": 1800, "happiness": 3600, "energy": 2700}
        for stat, period in periods.items():
            accumulated = int(self.decay_remainders.get(stat, 0)) + elapsed
            steps, remainder = divmod(accumulated, period)
            self.decay_remainders[stat] = remainder
            if steps:
                setattr(self, stat, getattr(self, stat) - steps)
                changed = True
        self.last_seen_at = now
        self._clamp_stats()
        return changed

    def perform_care(self, action, now=None):
        if self.life_status != "alive":
            return ActionOutcome(False, "Ciclo encerrado; escolha o ovo sucessor", action)
        if action not in ACTION_RULES:
            return ActionOutcome(False, "Ação desconhecida", action)
        now = int(time.time() if now is None else now)
        rule = ACTION_RULES[action]
        previous = int(self.last_action_at.get(action, 0))
        remaining = int(rule["cooldown"]) - (now - previous)
        if remaining > 0:
            return ActionOutcome(False, "Aguarde %ds" % remaining, action)
        if action == "feed" and self.hunger >= 98:
            return ActionOutcome(False, "Já está alimentado", action)
        if action == "play" and self.energy < 10:
            return ActionOutcome(False, "Sem energia para brincar", action)
        if action == "rest" and self.energy >= 98:
            return ActionOutcome(False, "Já está descansado", action)

        for stat, delta in rule["delta"].items():
            setattr(self, stat, getattr(self, stat) + delta)
        progression.grant(self, int(rule["xp"]))
        self.care_points += int(rule["care"])
        generations.add_affinity(self, "companionship", 1)
        self.last_action_at[action] = now
        self.action_counts[action] = int(self.action_counts.get(action, 0)) + 1
        self._clamp_stats()
        messages = {"feed": "Nhac! Fome restaurada", "play": "Diversão garantida", "rest": "Energia recuperada"}
        return ActionOutcome(True, messages[action], action)

