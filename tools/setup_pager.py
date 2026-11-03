#!/usr/bin/env python3
"""Deploy the app with a rollback copy; the save directory is never a target."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def deploy(source, payload_root, backup_root, library, manifest):
    source, parent, backups = Path(source).resolve(), Path(payload_root).resolve(), Path(backup_root).resolve()
    library = Path(library)
    expected = json.loads(Path(manifest).read_text(encoding="utf-8"))["sha256"]
    if hashlib.sha256(library.read_bytes()).hexdigest() != expected:
        raise ValueError("libpagerctl.so diferente da revisao fixada; nao instalada")
    # ELF32 little-endian MIPS. Actual ABI/load is checked separately on device.
    head = library.read_bytes()[:20]
    if head[:6] != b"\x7fELF\x01\x01" or head[18:20] != b"\x08\x00":
        raise ValueError("Biblioteca nao e ELF32 MIPS little-endian")
    target = parent / "hackomon"
    if source == target or target in source.parents or source in target.parents:
        raise ValueError("Origem e destino devem ser separados")
    if target.is_symlink():
        raise ValueError("Destino do payload e um link; nenhuma alteracao")
    parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(parent).free < 4 * 1024 * 1024:
        raise ValueError("Pouco espaco no armazenamento do payload")
    staging = Path(tempfile.mkdtemp(prefix=".hackomon-", dir=str(parent)))
    backup = None
    try:
        shutil.copytree(str(source), str(staging), dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (staging / "lib").mkdir(exist_ok=True)
        shutil.copyfile(str(library), str(staging / "lib" / "libpagerctl.so"))
        (staging / "payload.sh").chmod(0o755)
        (staging / "run_hackomon.py").chmod(0o755)
        if target.exists():
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / ("payload-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid()))
            if backup.exists():
                raise ValueError("Backup ja existe; repita a instalacao depois")
            os.rename(str(target), str(backup))
        try:
            os.rename(str(staging), str(target))
        except OSError:
            if backup and not target.exists():
                os.rename(str(backup), str(target))
            raise
    finally:
        if staging.exists():
            shutil.rmtree(str(staging))
    return target, backup


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme-base", type=Path)
    parser.add_argument("--skip-theme", action="store_true")
    args = parser.parse_args(argv)
    library = ROOT / "dependencies" / "libpagerctl.so"
    manifest = ROOT / "tools" / "pagerctl-dependency.json"
    # Validate imports and the pinned library load before deploying anything.
    sys.path.insert(0, str(ROOT / "payload" / "hackomon"))
    from hackomon.doctor import main as diagnose
    expected = json.loads(manifest.read_text(encoding="utf-8"))["sha256"]
    if not library.is_file() or hashlib.sha256(library.read_bytes()).hexdigest() != expected:
        parser.exit(2, "Biblioteca ausente/diferente. Execute Instalar-Hackomon.ps1 no Windows.\n")
    if diagnose(str(library)):
        parser.exit(2, "Dependencia obrigatoria falhou; payload/tema nao alterados.\n")
    target, backup = deploy(ROOT / "payload" / "hackomon", "/root/payloads/user/games",
                            "/mmc/root/hackomon-backups", library, manifest)
    print("Payload instalado: %s" % target)
    if backup:
        print("Payload anterior preservado: %s" % backup)
    # Theme failure does not falsely report the successful payload deployment as failed.
    if not args.skip_theme:
        spec = importlib.util.spec_from_file_location("install_theme", ROOT / "tools" / "install_theme.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        theme_args = ["--base", str(args.theme_base)] if args.theme_base else []
        try:
            module.main(theme_args)
        except SystemExit as error:
            print("AVISO: payload instalado; tema pendente (codigo %s). Veja o guia e o erro acima." % error.code)
            return 3
    print("Save/config preservados. Abra o Hackomon no menu Payloads > Games.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
