#!/usr/bin/env python3
"""Render PNG previews with only the Python standard library."""

import struct
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload" / "hackomon"
sys.path.insert(0, str(PAYLOAD))

from hackomon.catalog import CreatureCatalog  # noqa: E402
from hackomon.sprites import POSE_LENGTHS, palette_rgb, sprite_frame  # noqa: E402


BACKGROUND = (7, 12, 28)


def write_png(path, width, height, pixels):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue in row:
            raw.extend((red, green, blue))
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    payload += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def canvas(width, height):
    return [[BACKGROUND for _ in range(width)] for _ in range(height)]


def blit_sprite(target, creature, left, top, scale, pose="idle", frame_index=0):
    frame = sprite_frame(creature, pose, frame_index)
    palette = palette_rgb(creature)
    for y, row in enumerate(frame):
        for x, color_index in enumerate(row):
            if color_index == 0:
                continue
            color = palette[color_index]
            for sy in range(scale):
                for sx in range(scale):
                    target[top + y * scale + sy][left + x * scale + sx] = color


def render_bestiary(catalog, output):
    scale = 3
    cell = 24 * scale
    pixels = canvas(cell * 5, cell * 10)
    for index, evolution_line in enumerate(catalog.lines):
        creature = catalog.creature(evolution_line["creature_ids"][4])
        column = index % 5
        row = index // 5
        blit_sprite(pixels, creature, column * cell, row * cell, scale)
    write_png(output, cell * 5, cell * 10, pixels)


def render_animations(catalog, output):
    scale = 4
    cell = 24 * scale
    poses = tuple(POSE_LENGTHS)
    pixels = canvas(cell * 4, cell * len(poses))
    creature = catalog.creatures[249]
    for row, pose in enumerate(poses):
        for column in range(4):
            blit_sprite(pixels, creature, column * cell, row * cell, scale, pose, column)
    write_png(output, cell * 4, cell * len(poses), pixels)


def main():
    catalog = CreatureCatalog.load_default()
    images = ROOT / "docs" / "images"
    render_bestiary(catalog, images / "bestiary-preview.png")
    render_animations(catalog, images / "animation-preview.png")
    print("rendered previews in %s" % images)


if __name__ == "__main__":
    main()

