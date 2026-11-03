"""Exercise the actual Windows setup entry point using local SSH/TCP fixtures."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import threading
import unittest
from pathlib import Path

from tests import support


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe") and shutil.which("tar.exe"), "Windows installer integration")
class WindowsInstallerTests(unittest.TestCase):
    def test_cache_bundle_single_ssh_status_and_cleanup(self):
        with support.temporary_directory() as directory:
            root = Path(directory) / "bundle with spaces"
            root.mkdir()
            tools = root / "tools"
            tools.mkdir()
            for name in ("Instalar-Hackomon.ps1", "InstallerTransport.ps1", "setup_pager.sh"):
                shutil.copyfile(support.ROOT / "tools" / name, tools / name)
            payload = root / "payload/hackomon"
            payload.mkdir(parents=True)
            (payload / "payload.sh").write_text("fixture")
            (root / "themes").mkdir()
            (root / "themes/fixture.txt").write_text("fixture")
            dependency = root / "dependencies"
            dependency.mkdir()
            library = dependency / "libpagerctl.so"
            library.write_bytes(bytes(range(256)) * 100)
            digest = hashlib.sha256(library.read_bytes()).hexdigest()
            (tools / "pagerctl-dependency.json").write_text(json.dumps({
                "url": "https://must-not-download.invalid/library", "sha256": digest}))
            binaries = root / "bin"
            binaries.mkdir()
            compiler = root / "compile.ps1"
            fake = binaries / "ssh.exe"
            compiler.write_text('''$ErrorActionPreference = 'Stop'
$source = @'
using System;
using System.IO;
public class FakeSsh {
  public static int Main(string[] args) {
    File.AppendAllText(Environment.GetEnvironmentVariable("HACKOMON_TEST_CALLS"), "called\\n");
    using (var input = Console.OpenStandardInput())
    using (var output = File.Create(Environment.GetEnvironmentVariable("HACKOMON_TEST_ARCHIVE"))) { input.CopyTo(output); }
    return Int32.Parse(Environment.GetEnvironmentVariable("HACKOMON_TEST_EXIT"));
  }
}
'@
Add-Type -TypeDefinition $source -OutputAssembly (Join-Path $PSScriptRoot 'bin/ssh.exe') -OutputType ConsoleApplication
''', encoding="ascii")
            subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(compiler)], check=True, capture_output=True, timeout=30)
            env = os.environ.copy()
            env["PATH"] = str(binaries) + os.pathsep + env["PATH"]
            env["HACKOMON_TEST_CALLS"] = str(root / "calls.txt")
            env["HACKOMON_TEST_ARCHIVE"] = str(root / "received.tar")
            listener = socket.socket()
            try:
                listener.bind(("127.0.0.1", 22))
            except OSError:
                listener.close()
                self.skipTest("Local port 22 unavailable for read-only connection fixture")
            listener.listen(3)
            listener.settimeout(0.2)
            stopped = threading.Event()
            def accept_probe():
                while not stopped.is_set():
                    try:
                        connection, _ = listener.accept()
                        connection.close()
                    except socket.timeout:
                        pass
            thread = threading.Thread(target=accept_probe, daemon=True)
            thread.start()
            try:
                for code in (0, 3, 255):
                    env["HACKOMON_TEST_EXIT"] = str(code)
                    result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tools / "Instalar-Hackomon.ps1"), "-PagerAddress", "127.0.0.1"], env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code if code in (0, 3) else 2, result.stdout + result.stderr)
                    self.assertEqual(hashlib.sha256(library.read_bytes()).hexdigest(), digest)
                    self.assertFalse(list(dependency.glob("setup-*.tar")))
                    if code == 0:
                        self.assertIn("PRONTO!", result.stdout)
                    else:
                        self.assertNotIn("PRONTO!", result.stdout)
                    if code == 3:
                        self.assertIn("APP INSTALADO", result.stdout)
            finally:
                stopped.set()
                thread.join(timeout=1)
                listener.close()
            self.assertEqual((root / "calls.txt").read_text().splitlines(), ["called"] * 3)
            import tarfile
            with tarfile.open(root / "received.tar") as archive:
                self.assertIn("payload/hackomon/payload.sh", archive.getnames())
                self.assertIn("tools/setup_pager.sh", archive.getnames())
                self.assertEqual(archive.extractfile("dependencies/libpagerctl.so").read(), library.read_bytes())
