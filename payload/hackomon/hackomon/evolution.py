"""Evolution gates for the five-stage Hackomon lines."""

from dataclasses import dataclass


GATES = {
    1: {"level": 3, "care": 4, "wellness": 0},
    2: {"level": 6, "care": 10, "wellness": 35},
    3: {"level": 10, "care": 20, "wellness": 45},
    4: {"level": 15, "care": 35, "wellness": 55},
}


@dataclass
class EvolutionResult:
    evolved: bool
    previous_id: str
    creature_id: str
    reason: str


def next_gate(state):
    return GATES.get(state.stage + 1)


def gate_status(state):
    gate = next_gate(state)
    if gate is None:
        return None
    return {
        "level": (state.level, gate["level"]),
        "care": (state.care_points, gate["care"]),
        "wellness": (state.wellness, gate["wellness"]),
    }


def advance_one_if_ready(state, catalog):
    gate = next_gate(state)
    if gate is None:
        return EvolutionResult(False, state.creature_id, state.creature_id, "forma final")
    if state.level < gate["level"]:
        return EvolutionResult(False, state.creature_id, state.creature_id, "nível insuficiente")
    if state.care_points < gate["care"]:
        return EvolutionResult(False, state.creature_id, state.creature_id, "cuidados insuficientes")
    if state.wellness < gate["wellness"]:
        return EvolutionResult(False, state.creature_id, state.creature_id, "bem-estar insuficiente")

    previous_id = state.creature_id
    state.stage += 1
    creature = catalog.creature_for_stage(state.line_id, state.stage)
    state.creature_id = creature["id"]
    if creature["id"] not in state.discovered:
        state.discovered.append(creature["id"])
    state.happiness = min(100, state.happiness + 12)
    state.energy = min(100, state.energy + 8)
    return EvolutionResult(True, previous_id, creature["id"], "evolução concluída")

