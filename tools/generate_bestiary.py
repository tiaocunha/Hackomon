#!/usr/bin/env python3
"""Generate the deterministic Hackomon bestiary used on the Pager."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "payload" / "hackomon" / "data" / "bestiary.json"

STAGES = (
    (0, "Ovo", "common"),
    (1, "Filhote", "common"),
    (2, "Jovem", "uncommon"),
    (3, "Adulto", "rare"),
    (4, "Forma rara", "mythic"),
)


def line(line_id, title, root, palette, motif, temperament):
    return {
        "id": line_id,
        "name": title,
        "root": root,
        "palette": palette,
        "motif": motif,
        "temperament": temperament,
    }


FAMILIES = (
    {
        "id": "slime",
        "name": "Geleias",
        "shape": "blob",
        "description": "Criaturas elásticas que condensam energia do ambiente.",
        "lines": (
            line("lumen", "Lúmen", "Lúmen", ["#6DE8D2", "#B8FFF3", "#FFF27A"], "spark", "curious"),
            line("volt", "Voltaico", "Volt", ["#2E5BFF", "#7DE7FF", "#FFF15A"], "bolt", "bold"),
            line("miasma", "Miasma", "Miasma", ["#78C850", "#C8FF72", "#8A4FFF"], "spots", "calm"),
            line("crystal", "Cristal", "Crista", ["#73B9FF", "#E5F5FF", "#FF79C6"], "crystal", "proud"),
            line("abyss", "Abissal", "Abiss", ["#26134D", "#7149A8", "#26F7D4"], "tentacle", "shy"),
        ),
    },
    {
        "id": "mammal",
        "name": "Mamíferos",
        "shape": "mammal",
        "description": "Companheiros ágeis com orelhas, caudas e forte vínculo afetivo.",
        "lines": (
            line("fox", "Raposa Solar", "Solrap", ["#F48B32", "#FFD07A", "#FFF4D2"], "flame", "clever"),
            line("cat", "Felino Noturno", "Noxfel", ["#2E294E", "#6D5AA8", "#6EF2FF"], "moon", "aloof"),
            line("rabbit", "Coelho Nimbo", "Nimbol", ["#E8E8F4", "#FFFFFF", "#83D9FF"], "cloud", "playful"),
            line("bear", "Urso Musgo", "Musgurso", ["#6B4F32", "#A77B52", "#74C365"], "leaf", "gentle"),
            line("wolf", "Lobo Boreal", "Borilobo", ["#7896B8", "#DCEBFF", "#55E6C1"], "aurora", "loyal"),
        ),
    },
    {
        "id": "avian",
        "name": "Aves",
        "shape": "avian",
        "description": "Aves pequenas que acumulam vento, som e luz nas penas.",
        "lines": (
            line("crow", "Corvo Glitch", "Corvix", ["#181825", "#4B4B70", "#FF4FD8"], "glitch", "wary"),
            line("sunbird", "Pássaro Solar", "Heliave", ["#F6B73C", "#FFF06A", "#FF6B35"], "sun", "bright"),
            line("storm", "Falcão Tempestade", "Torval", ["#4059AD", "#8EA7E9", "#F7E733"], "bolt", "bold"),
            line("owl", "Coruja Oráculo", "Oracoru", ["#7C5C45", "#CBAF87", "#71E5FF"], "rune", "wise"),
            line("humming", "Beija-flor Prisma", "Prismel", ["#15B097", "#8BFFDE", "#FF79C6"], "prism", "energetic"),
        ),
    },
    {
        "id": "reptile",
        "name": "Répteis",
        "shape": "reptile",
        "description": "Escamas resistentes e evoluções marcadas por chifres e caudas.",
        "lines": (
            line("dragon", "Dragão Brasa", "Brasagon", ["#A43A2B", "#F06A35", "#FFD166"], "horn", "fierce"),
            line("gecko", "Lagarto Neon", "Geckon", ["#47D16C", "#9DFF73", "#FF4FD8"], "spots", "nimble"),
            line("turtle", "Tartaruga Runa", "Runatur", ["#3B7A57", "#82C091", "#F4D35E"], "rune", "patient"),
            line("serpent", "Serpente Coral", "Coralisk", ["#E63946", "#F1FAEE", "#1D3557"], "bands", "focused"),
            line("chameleon", "Camaleão Pixel", "Camapix", ["#5BC0BE", "#9BF6A3", "#FF8FAB"], "pixel", "adaptable"),
        ),
    },
    {
        "id": "aquatic",
        "name": "Aquáticos",
        "shape": "aquatic",
        "description": "Habitantes de poças digitais, correntes e mares imaginários.",
        "lines": (
            line("axolotl", "Axolote Aurora", "Axolume", ["#FF9EC4", "#FFD3E4", "#6EE7F2"], "gill", "friendly"),
            line("koi", "Koi Celeste", "Koilum", ["#F6F7FF", "#FF754B", "#65C7F7"], "wave", "serene"),
            line("shark", "Tubarão Byte", "Bytubar", ["#437F97", "#9CC5D5", "#D8FF3E"], "byte", "hungry"),
            line("frog", "Sapo Chuva", "Pluvapo", ["#5FBF70", "#A8E6A3", "#4EA5D9"], "drop", "cheerful"),
            line("manta", "Manta Vazio", "Mantavoid", ["#312A63", "#6457A6", "#64F4D2"], "star", "quiet"),
        ),
    },
    {
        "id": "insect",
        "name": "Insetos",
        "shape": "insect",
        "description": "Pequenos construtores com asas, antenas e carapaças vívidas.",
        "lines": (
            line("bee", "Abelha Âmbar", "Ambeia", ["#F5B700", "#FFF07C", "#3A2E39"], "bands", "busy"),
            line("moth", "Mariposa Lunar", "Luniposa", ["#6C5B7B", "#C7B8EA", "#E9FF70"], "moon", "dreamy"),
            line("beetle", "Besouro Cromo", "Cromouro", ["#1F6F78", "#68C3A3", "#F7D774"], "shell", "steady"),
            line("mantis", "Louva-a-deus Jade", "Jadantis", ["#4C956C", "#A3E635", "#F2C14E"], "blade", "focused"),
            line("firefly", "Vaga-lume Pulso", "Lumpulso", ["#273043", "#475B63", "#D9FF57"], "spark", "hopeful"),
        ),
    },
    {
        "id": "spectral",
        "name": "Espectros",
        "shape": "spectral",
        "description": "Ecos gentis que habitam ruídos, sonhos e sinais esquecidos.",
        "lines": (
            line("wisp", "Fogo-fátuo", "Fatuo", ["#7AE7C7", "#C8FFF0", "#7067CF"], "flame", "curious"),
            line("polter", "Polter Ruído", "Polter", ["#B8B8FF", "#E8E8FF", "#FF4FD8"], "noise", "mischief"),
            line("dream", "Sonho Azul", "Onirul", ["#6C63FF", "#A9A5FF", "#FFD6FF"], "cloud", "dreamy"),
            line("shadow", "Sombra Eco", "Umbraco", ["#171325", "#433A60", "#49F2C2"], "echo", "shy"),
            line("lantern", "Lanterna Alma", "Almaluz", ["#E07A2D", "#FFD166", "#F7F7C4"], "lantern", "warm"),
        ),
    },
    {
        "id": "botanical",
        "name": "Flora e Fungos",
        "shape": "botanical",
        "description": "Brotos pacientes que florescem com cuidado regular.",
        "lines": (
            line("mushroom", "Cogumelo Orvalho", "Orvafungo", ["#C65D7B", "#F6B8C9", "#8EC07C"], "spots", "gentle"),
            line("cactus", "Cacto Cometa", "Cacteta", ["#4F9D69", "#8CD790", "#FFD166"], "star", "tough"),
            line("flower", "Flor Prisma", "Priflor", ["#FF6FAE", "#FFD1E8", "#62D2A2"], "prism", "bright"),
            line("vine", "Cipó Circuito", "Circipó", ["#3E8E5B", "#8FDB78", "#4DD0E1"], "circuit", "clever"),
            line("moss", "Musgo Antigo", "Antramus", ["#526B2D", "#91A35A", "#D4C685"], "rune", "wise"),
        ),
    },
    {
        "id": "robotic",
        "name": "Robóticos",
        "shape": "robotic",
        "description": "Autômatos compactos que aprendem rotinas de cuidado.",
        "lines": (
            line("drone", "Drone Íon", "Ionix", ["#596275", "#A5B1C2", "#26DE81"], "antenna", "alert"),
            line("gear", "Engrenagem Viva", "Cogvita", ["#6D6875", "#B0A8B9", "#FFB703"], "gear", "steady"),
            line("radio", "Rádio Eco", "Radioco", ["#264653", "#5C8D89", "#E9C46A"], "signal", "curious"),
            line("sentinel", "Sentinela Rubi", "Rubinel", ["#3D405B", "#777B9E", "#E63946"], "shield", "loyal"),
            line("synth", "Sintético Prisma", "Synthra", ["#20223A", "#5B5FEF", "#FF4FD8"], "prism", "creative"),
        ),
    },
    {
        "id": "cosmic",
        "name": "Cósmicos",
        "shape": "cosmic",
        "description": "Anomalias fofas nascidas entre estrelas e pacotes perdidos.",
        "lines": (
            line("star", "Estrela Pulso", "Pulsar", ["#355CDE", "#88A7FF", "#FFF06A"], "star", "bright"),
            line("comet", "Cometa Íris", "Iricom", ["#6A4C93", "#B48EED", "#4DEEEA"], "trail", "energetic"),
            line("void", "Vazio Gentil", "Voidim", ["#0B1026", "#30365C", "#64F4D2"], "orbit", "quiet"),
            line("moon", "Lua Broto", "Lunabro", ["#C9D6EA", "#F4F7FF", "#8DD7CF"], "leaf", "gentle"),
            line("nebula", "Nebulosa Doce", "Nebulita", ["#7B2CBF", "#C77DFF", "#FF85A1"], "cloud", "dreamy"),
        ),
    },
)


def creature_name(root, stage):
    patterns = (
        "Ovo {0}",
        "{0}in",
        "{0}on",
        "{0}arca",
        "{0} Ômega",
    )
    return patterns[stage].format(root)


def stable_seed(value):
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def build_catalog():
    catalog_families = []
    catalog_lines = []
    creatures = []
    creature_index = 0

    for family_index, family in enumerate(FAMILIES):
        catalog_families.append(
            {
                "id": family["id"],
                "index": family_index,
                "name": family["name"],
                "shape": family["shape"],
                "description": family["description"],
            }
        )
        for family_line_index, source_line in enumerate(family["lines"]):
            line_id = "%s-%s" % (family["id"], source_line["id"])
            creature_ids = []
            for stage, stage_name, rarity in STAGES:
                creature_id = "%s-s%d" % (line_id, stage)
                creature_ids.append(creature_id)
                creatures.append(
                    {
                        "id": creature_id,
                        "index": creature_index,
                        "family_id": family["id"],
                        "line_id": line_id,
                        "stage": stage,
                        "stage_name": stage_name,
                        "name": creature_name(source_line["root"], stage),
                        "rarity": rarity,
                        "temperament": source_line["temperament"],
                        "sprite": {
                            "shape": family["shape"],
                            "motif": source_line["motif"],
                            "palette": source_line["palette"],
                            "seed": stable_seed(creature_id),
                            "variant": family_line_index,
                            "growth": stage,
                        },
                    }
                )
                creature_index += 1

            catalog_lines.append(
                {
                    "id": line_id,
                    "family_id": family["id"],
                    "family_line_index": family_line_index,
                    "name": source_line["name"],
                    "temperament": source_line["temperament"],
                    "motif": source_line["motif"],
                    "creature_ids": creature_ids,
                }
            )

    return {
        "schema_version": 1,
        "counts": {"families": 10, "lines": 50, "creatures": 250, "stages_per_line": 5},
        "families": catalog_families,
        "lines": catalog_lines,
        "creatures": creatures,
    }


def serialized_catalog():
    return json.dumps(build_catalog(), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the checked-in catalog is stale")
    args = parser.parse_args()
    expected = serialized_catalog()

    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("bestiary.json is missing or stale; run tools/generate_bestiary.py")
        print("bestiary.json is current")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
    print("wrote %s (%d creatures)" % (OUTPUT, len(build_catalog()["creatures"])))


if __name__ == "__main__":
    main()

