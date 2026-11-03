# Run with Windows PowerShell 5.1. A local fake SSH executable receives bytes;
# no Pager, network connection, credentials or downloaded executable is used.
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $repoRoot 'tools/InstallerTransport.ps1')
$testRoot = Join-Path $repoRoot ('.test-tmp/transport with spaces-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$fakeSsh = Join-Path $testRoot 'fake ssh.exe'
$source = @'
using System;
using System.IO;
public class FakeSsh {
    public static int Main(string[] args) {
        File.WriteAllLines(Environment.GetEnvironmentVariable("HACKOMON_TEST_ARGS"), args);
        if (Environment.GetEnvironmentVariable("HACKOMON_TEST_EARLY") == "1") return 255;
        using (var input = Console.OpenStandardInput())
        using (var output = File.Create(Environment.GetEnvironmentVariable("HACKOMON_TEST_OUTPUT"))) {
            input.CopyTo(output);
        }
        return Int32.Parse(Environment.GetEnvironmentVariable("HACKOMON_TEST_EXIT"));
    }
}
'@
Add-Type -TypeDefinition $source -OutputAssembly $fakeSsh -OutputType ConsoleApplication
$archive = Join-Path $testRoot 'archive with spaces.tar'
$bytes = New-Object byte[] (1024 * 1024 + 137)
for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = $i % 256 }
[System.IO.File]::WriteAllBytes($archive, $bytes)
$knownHashFile = Join-Path $testRoot 'abc.bin'
[System.IO.File]::WriteAllBytes($knownHashFile, [System.Text.Encoding]::ASCII.GetBytes('abc'))
if ((Get-HackomonSha256 $knownHashFile) -ne 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad') { throw 'SHA-256 implementation failed' }
$env:HACKOMON_TEST_ARGS = Join-Path $testRoot 'args.txt'
$env:HACKOMON_TEST_OUTPUT = Join-Path $testRoot 'received.bin'
foreach ($code in @(0, 3, 255)) {
    $env:HACKOMON_TEST_EXIT = [string]$code
    $result = Send-HackomonArchive -Archive $archive -PagerAddress '172.16.52.1' -Destination '/mmc/root/hackomon-setup-0.8.1' -SshPath $fakeSsh -SkipTheme:($code -eq 3)
    if ($result -ne $code) { throw "SSH status changed: expected $code, got $result" }
    if ((Get-HackomonSha256 $archive) -ne (Get-HackomonSha256 $env:HACKOMON_TEST_OUTPUT)) { throw 'Binary archive corrupted in transport' }
    $receivedArgs = [System.IO.File]::ReadAllLines($env:HACKOMON_TEST_ARGS)
    if ($receivedArgs.Length -ne 6 -or $receivedArgs[4] -ne 'root@172.16.52.1') { throw 'SSH arguments incorrectly quoted' }
    if (-not $receivedArgs[5].Contains("tar -xf - -C '/mmc/root/hackomon-setup-0.8.1'")) { throw 'Missing remote extraction' }
    if (-not $receivedArgs[5].EndsWith('</dev/null')) { throw 'Setup must not consume archive input' }
    if ($receivedArgs[5].Contains('--skip-theme') -ne ($code -eq 3)) { throw 'SkipTheme not propagated correctly' }
}
$env:HACKOMON_TEST_EARLY = '1'
$result = Send-HackomonArchive -Archive $archive -PagerAddress '172.16.52.1' -Destination '/mmc/root/hackomon-setup-0.8.1' -SshPath $fakeSsh
if ($result -ne 255) { throw 'Early SSH failure was not preserved' }
$env:HACKOMON_TEST_EARLY = '0'
$rejected = $false
try { Send-HackomonArchive -Archive $archive -PagerAddress 'bad;host' -Destination '/mmc/root/hackomon-setup-0.8.1' -SshPath $fakeSsh }
catch [System.Management.Automation.ParameterBindingException] { $rejected = $true }
if (-not $rejected) { throw 'Unsafe host was accepted' }
Write-Host 'PASS: binary transfer, paths with spaces, SSH argument quoting, exit 0/3/255, early disconnect, SkipTheme and invalid host rejection.'
