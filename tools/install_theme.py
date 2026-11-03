#!/usr/bin/env python3
"""Build a local theme derivative without distributing the Hak5 base theme."""

import argparse
import json
import os
import re
import shutil
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "themes" / "hackomon-field"
BASES = (
    "/lib/pager/themes/wargames",
    "/root/themes/wargames", "/mmc/root/themes/wargames",
    "/usr/share/pineapplepager/themes/wargames", "/usr/share/themes/wargames",
    "/rom/root/themes/wargames",
)


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def local_file(base, relative):
    if not isinstance(relative, str) or "\\" in relative:
        raise ValueError("Referencia de tema invalida")
    candidate = (base / relative).resolve()
    if Path(relative).is_absolute() or base.resolve() not in candidate.parents:
        raise ValueError("Referencia fora do tema: %s" % relative)
    if not candidate.is_file():
        raise ValueError("Arquivo ausente: %s" % relative)
    return candidate


def validate_references(base, value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key == "image_path" or item.startswith(("components/", "assets/"))):
                local_file(base, item)
            else:
                validate_references(base, item)
    elif isinstance(value, list):
        for item in value:
            validate_references(base, item)


def prepare(base, overlay=OVERLAY):
    base, overlay = Path(base).resolve(), Path(overlay).resolve()
    theme = read_json(base / "theme.json")
    if theme.get("theme_framework_version") != "0.9" or theme.get("theme_version") != "2.0.0":
        raise ValueError("Base diferente do formato 2.0.0 / framework 0.9; nao foi alterada.")
    dashboard_rel = theme["generic_menus"]["dashboard_path"]
    lock_rel = theme["lock_screen_path"]
    dashboard = read_json(local_file(base, dashboard_rel))
    lock = read_json(local_file(base, lock_rel))
    if dashboard.get("screen_name") != "main_dashboard" or lock.get("screen_name") != "lock_screen":
        raise ValueError("Telas base nao reconhecidas")
    # This overlay was composed around the stock Wargames six-icon layout.
    expected = {"pagerportal": (227, 116), "ALERTS": (263, 79), "PAYLOADS": (299, 116),
                "RECON": (335, 80), "PINEAP": (373, 115), "SETTINGS": (410, 80)}
    actual = {item.get("id"): (item.get("x"), item.get("y")) for item in dashboard.get("menu_items", [])}
    if actual != expected:
        raise ValueError("Layout base diferente do Wargames 2.0; use a base original do firmware.")
    for path in base.rglob("*.json"):
        validate_references(base, read_json(path))
    for path in base.rglob("*"):
        # Only self-contained local assets; never follow links outside the licensed base.
        if path.is_symlink():
            raise ValueError("Base contem link simbolico: %s" % path.relative_to(base))
    image = local_file(overlay, "assets/field.png").read_bytes()
    if image[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", image[16:24]) != (480, 222):
        raise ValueError("O fundo deve ser PNG de 480x222")
    palette = read_json(overlay / "palette.json")
    for color in palette.values():
        if set(color) != {"r", "g", "b"} or any(type(n) is not int or not 0 <= n <= 255 for n in color.values()):
            raise ValueError("Paleta RGB invalida")
    theme["color_palette"].update(palette)
    # Preserve firmware version fields, every target, variable, control and status bar.
    dashboard["background"]["layers"] = [
        {"image_path": "assets/hackomon/field.png", "x": 0, "y": 0},
        {"text": "HACKOMON", "x": 16, "y": 30, "text_size": "large", "text_color_palette": "blue"},
        {"text": "FIELD COMPANION", "x": 17, "y": 53, "text_size": "small", "text_color_palette": "gray"},
    ]
    lock["background"]["layers"] = [
        {"image_path": "assets/hackomon/field.png", "x": 0, "y": 0},
        {"text": "HACKOMON", "x": 254, "y": 62, "text_size": "large", "text_color_palette": "blue"},
        {"text": "FIELD COMPANION", "x": 255, "y": 87, "text_size": "small", "text_color_palette": "gray"},
    ]
    items = lock.get("pages", [{}])[0].get("menu_items", [])
    if len(items) != 1 or items[0].get("id") != "lock_screen":
        raise ValueError("Bloqueio base nao reconhecido")
    items[0]["selected_layers"] = [
        {"text": "Press 'A'\nto unlock", "x": 255, "y": 124,
         "text_color_palette": "yellow", "text_size": "small", "wrap_text": True, "max_lines": 2}
    ]
    return theme, dashboard_rel, dashboard, lock_rel, lock


def install(base, themes_root, name="hackomon-field", overlay=OVERLAY, dry_run=False):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name):
        raise ValueError("Nome deve usar letras minusculas, numeros e hifen")
    base, parent = Path(base).resolve(), Path(themes_root).resolve()
    target = parent / name
    if target.exists() or target.is_symlink():
        raise ValueError("Destino ja existe; nada sobrescrito: %s" % target)
    if target == base or target in base.parents or base in target.parents:
        raise ValueError("Destino e base devem ser separados")
    values = prepare(base, overlay)
    size = sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
    if dry_run:
        return {"target": str(target), "base": str(base), "base_bytes": size, "dry_run": True}
    parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(parent).free < size + 2 * 1024 * 1024:
        raise ValueError("Espaco insuficiente para uma copia independente do tema")
    staging = Path(tempfile.mkdtemp(prefix=".hackomon-", dir=str(parent)))
    try:
        shutil.copytree(str(base), str(staging), dirs_exist_ok=True)
        (staging / "assets" / "hackomon").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(Path(overlay) / "assets" / "field.png"), str(staging / "assets" / "hackomon" / "field.png"))
        theme, dash_rel, dash, lock_rel, lock = values
        write_json(staging / "theme.json", theme)
        write_json(staging / dash_rel, dash)
        write_json(staging / lock_rel, lock)
        write_json(staging / "hackomon-overlay.json", {"name": name, "overlay_version": "0.8.0", "base": str(base), "hardware_validated": False})
        if (staging / "README").is_file():
            shutil.copyfile(str(staging / "README"), str(staging / "README-BASE-Hak5.txt"))
        shutil.copyfile(str(Path(overlay) / "README.md"), str(staging / "README"))
        for path in staging.rglob("*.json"):
            validate_references(staging, read_json(path))
        # rename cannot replace a populated theme directory; never remove the destination.
        if target.exists() or target.is_symlink():
            raise ValueError("Destino criado por outra instalacao; nada sobrescrito")
        os.rename(str(staging), str(target))
    finally:
        if staging.exists():
            shutil.rmtree(str(staging))
    return {"target": str(target), "base": str(base), "base_bytes": size, "dry_run": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Criar tema Hackomon a partir da base local licenciada Hak5")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--themes-root", type=Path, default=Path("/root/themes"))
    parser.add_argument("--name", default="hackomon-field")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    base = args.base or next((Path(p) for p in BASES if (Path(p) / "theme.json").is_file()), None)
    if not base:
        parser.exit(2, "Base Wargames nao encontrada. Indique --base /caminho/do/tema/wargames\n")
    try:
        result = install(base, args.themes_root, args.name, dry_run=args.dry_run)
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        parser.exit(2, "Tema nao instalado: %s\n" % error)
    print(json.dumps(result, indent=2))
    if not args.dry_run:
        print("Selecione Settings > General > Theme > %s. A selecao nao foi alterada." % args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
