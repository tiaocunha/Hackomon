#!/usr/bin/env python3
"""Build the copy-ready Pager payload archive."""

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload" / "hackomon"
DIST = ROOT / "dist"
OUTPUT = DIST / "hackomon-pager-0.8.6.zip"
SETUP = DIST / "hackomon-instalar-0.8.6.zip"


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
        archive.write(ROOT / "docs" / "EXPEDITIONS.md", "EXPEDITIONS.md")
        archive.write(ROOT / "docs" / "WDGWARS.md", "WDGWARS.md")
        archive.write(ROOT / "docs" / "TESTE_RAPIDO.txt", "LEIA_PRIMEIRO.txt")
    print("built %s" % OUTPUT)
    with zipfile.ZipFile(SETUP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for folder in ("payload", "themes"):
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ("install_theme.py", "setup_pager.py", "setup_pager.sh", "Instalar-Hackomon.ps1", "InstallerTransport.ps1", "pagerctl-dependency.json", "Diagnosticar-Hackomon.ps1", "diagnose_radios.py"):
            archive.write(ROOT / "tools" / name, "tools/" + name)
        for path in sorted((ROOT / "docs").glob("*.md")):
            archive.write(path, "docs/" + path.name)
        guide = (ROOT / "docs" / "INSTALAR_2_0.md").read_text(encoding="utf-8")
        guide = guide.replace("(NETWORKS.md)", "(docs/NETWORKS.md)").replace("(EXPEDITIONS.md)", "(docs/EXPEDITIONS.md)")
        archive.writestr("COMECE_AQUI.md", guide)
        # Batch entry point must be directly usable by Windows after extracting the ZIP.
        archive.writestr("INSTALAR.cmd", (ROOT / "INSTALAR.cmd").read_text().replace("\r\n", "\n").replace("\n", "\r\n"))
        archive.writestr("DIAGNOSTICAR.cmd", (ROOT / "DIAGNOSTICAR.cmd").read_text().replace("\r\n", "\n").replace("\n", "\r\n"))
        archive.write(ROOT / "LEIA_PRIMEIRO.txt", "LEIA_PRIMEIRO.txt")
        for name in ("LICENSE", "THIRD_PARTY.md"):
            archive.write(ROOT / name, name)
    print("built %s" % SETUP)


if __name__ == "__main__":
    main()

