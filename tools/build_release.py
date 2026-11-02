#!/usr/bin/env python3
"""Build the copy-ready Pager payload archive."""

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload" / "hackomon"
DIST = ROOT / "dist"
OUTPUT = DIST / "hackomon-pager-0.4.1.zip"


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PAYLOAD.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            relative = Path("hackomon") / path.relative_to(PAYLOAD)
            info = zipfile.ZipInfo.from_file(path, str(relative).replace("\\", "/"))
            if path.name == "payload.sh" or path.name == "run_hackomon.py":
                info.external_attr = 0o100755 << 16
            with path.open("rb") as handle:
                archive.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for name in ("LICENSE", "THIRD_PARTY.md"):
            archive.write(ROOT / name, name)
        archive.write(ROOT / "docs" / "INSTALL.md", "INSTALL.md")
        archive.write(ROOT / "docs" / "HARDWARE_VALIDATION.md", "HARDWARE_VALIDATION.md")
        archive.write(ROOT / "docs" / "NETWORKS.md", "NETWORKS.md")
    print("built %s" % OUTPUT)


if __name__ == "__main__":
    main()

