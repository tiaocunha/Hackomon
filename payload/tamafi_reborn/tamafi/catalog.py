"""Load and validate the compact 250-creature bestiary."""

import json
from pathlib import Path


class CatalogError(ValueError):
    pass


class CreatureCatalog:
    def __init__(self, raw):
        self.raw = raw
        self.families = tuple(raw.get("families", ()))
        self.lines = tuple(raw.get("lines", ()))
        self.creatures = tuple(raw.get("creatures", ()))
        self.family_by_id = {item["id"]: item for item in self.families}
        self.line_by_id = {item["id"]: item for item in self.lines}
        self.creature_by_id = {item["id"]: item for item in self.creatures}
        self.validate()

    @classmethod
    def from_path(cls, path):
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    @classmethod
    def load_default(cls):
        path = Path(__file__).resolve().parents[1] / "data" / "bestiary.json"
        return cls.from_path(path)

    def validate(self):
        if self.raw.get("schema_version") != 1:
            raise CatalogError("unsupported catalog schema")
        if len(self.families) != 10:
            raise CatalogError("catalog must contain 10 families")
        if len(self.lines) != 50:
            raise CatalogError("catalog must contain 50 evolutionary lines")
        if len(self.creatures) != 250:
            raise CatalogError("catalog must contain 250 creatures")
        if len(self.family_by_id) != 10 or len(self.line_by_id) != 50:
            raise CatalogError("family and line IDs must be unique")
        if len(self.creature_by_id) != 250:
            raise CatalogError("creature IDs must be unique")
        if len({item["name"] for item in self.creatures}) != 250:
            raise CatalogError("creature names must be unique")

        expected_indices = set(range(250))
        if {item.get("index") for item in self.creatures} != expected_indices:
            raise CatalogError("creature indices must be contiguous")

        for evolution_line in self.lines:
            family_id = evolution_line.get("family_id")
            ids = evolution_line.get("creature_ids", ())
            if family_id not in self.family_by_id:
                raise CatalogError("unknown family on line %s" % evolution_line.get("id"))
            if len(ids) != 5:
                raise CatalogError("line %s must contain 5 stages" % evolution_line.get("id"))
            for stage, creature_id in enumerate(ids):
                creature = self.creature_by_id.get(creature_id)
                if creature is None:
                    raise CatalogError("unknown creature %s" % creature_id)
                if creature["line_id"] != evolution_line["id"]:
                    raise CatalogError("creature assigned to the wrong line")
                if creature["family_id"] != family_id or creature["stage"] != stage:
                    raise CatalogError("creature family/stage mismatch")
                sprite = creature.get("sprite", {})
                if len(sprite.get("palette", ())) != 3:
                    raise CatalogError("sprite palette must have exactly three colors")

    def creature(self, creature_id):
        try:
            return self.creature_by_id[creature_id]
        except KeyError as error:
            raise CatalogError("unknown creature: %s" % creature_id) from error

    def evolution_line(self, line_id):
        try:
            return self.line_by_id[line_id]
        except KeyError as error:
            raise CatalogError("unknown evolutionary line: %s" % line_id) from error

    def creature_for_stage(self, line_id, stage):
        evolution_line = self.evolution_line(line_id)
        if not 0 <= stage < 5:
            raise CatalogError("stage must be from 0 through 4")
        return self.creature(evolution_line["creature_ids"][stage])

    def family_lines(self, family_id):
        return tuple(item for item in self.lines if item["family_id"] == family_id)

