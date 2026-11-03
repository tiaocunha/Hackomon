param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*$')]
    [string]$PagerAddress = '172.16.52.1',
    [switch]$SkipTheme
)
$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pagerctl-dependency.json') -Raw | ConvertFrom-Json
foreach ($command in @('ssh', 'scp')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Instale o Cliente OpenSSH do Windows: falta $command." }
}
if (-not (Test-Path -LiteralPath (Join-Path $bundleRoot 'payload/hackomon/payload.sh'))) { throw 'Extraia o pacote completo antes de executar.' }
$dependencyDir = Join-Path $bundleRoot 'dependencies'
New-Item -ItemType Directory -Force -Path $dependencyDir | Out-Null
$library = Join-Path $dependencyDir 'libpagerctl.so'
Write-Host 'Baixando a biblioteca de tela PAGERCTL da revisao fixada no guia...'
Invoke-WebRequest -Uri $manifest.url -OutFile $library
if ((Get-FileHash -LiteralPath $library -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256) {
    throw 'A biblioteca baixada nao corresponde ao SHA-256 esperado. Nada enviado ao Pager.'
}
$remote = "root@$PagerAddress"
$destination = '/mmc/root/hackomon-setup-0.8.0'
Write-Host 'Conectando ao seu Pager. Use a senha criada na configuracao inicial.'
& ssh $remote "mkdir -p '$destination'"
if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel conectar/criar a pasta de preparo.' }
# Legacy SCP mode also works with Pager installations without an SFTP subsystem.
& scp -O -r (Join-Path $bundleRoot 'payload') (Join-Path $bundleRoot 'themes') (Join-Path $bundleRoot 'tools') $dependencyDir "${remote}:$destination/"
if ($LASTEXITCODE -ne 0) { throw 'Copia incompleta. A instalacao nao foi iniciada.' }
$setupCommand = "sh '$destination/tools/setup_pager.sh' --deps"
if ($SkipTheme) { $setupCommand += ' --skip-theme' }
& ssh $remote $setupCommand
$result = $LASTEXITCODE
if ($result -eq 3) { Write-Warning 'O app foi instalado, mas o tema ficou pendente. Veja a mensagem acima e o guia.'; exit 3 }
if ($result -ne 0) { throw "Instalacao interrompida (codigo $result). Veja a primeira mensagem de erro acima." }
Write-Host 'Instalacao concluida. Tema: Settings > General > Theme > hackomon-field.'
Write-Host 'App: Payloads > Games > Hackomon. Teste primeiro os botoes e a volta ao menu.'
