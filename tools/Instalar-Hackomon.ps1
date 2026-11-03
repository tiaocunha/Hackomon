param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*$')]
    [string]$PagerAddress = '172.16.52.1',
    [switch]$SkipTheme
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'InstallerTransport.ps1')
$bundleRoot = Split-Path -Parent $PSScriptRoot
$archive = $null
try {
    Write-Host ''
    Write-Host 'HACKOMON - INSTALACAO FACIL' -ForegroundColor Cyan
    Write-Host 'Conecte o Pager por USB-C de dados ou pelo Wi-Fi de gerenciamento.'
    Write-Host 'No Pager: SSH ativado. Internet se precisar instalar dependencias ausentes.'
    Write-Host 'Deixe o Hackomon fechado durante a instalacao.'
    Write-Host ''
    $ssh = @(Get-Command ssh.exe -CommandType Application -ErrorAction SilentlyContinue)[0]
    $tar = @(Get-Command tar.exe -CommandType Application -ErrorAction SilentlyContinue)[0]
    if (-not $ssh) { throw 'Falta o Cliente OpenSSH do Windows. Ative-o em Configuracoes > Recursos opcionais e abra INSTALAR.cmd novamente.' }
    if (-not $tar) { throw 'Falta tar.exe do Windows 10/11. Consulte a instalacao manual em docs/INSTALL.md.' }
    if (-not (Test-Path -LiteralPath (Join-Path $bundleRoot 'payload/hackomon/payload.sh'))) { throw 'Extraia TODO o ZIP antes de abrir INSTALAR.cmd.' }
    Write-Host '[1/3] Procurando o Pager...'
    if (-not (Test-HackomonConnection $PagerAddress)) {
        throw 'Pager nao encontrado. Confira o cabo de dados ou Wi-Fi de gerenciamento e ative Settings > System > SSH. Depois abra INSTALAR.cmd novamente.'
    }
    Write-Host '[2/3] Preparando os arquivos...'
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'pagerctl-dependency.json') -Raw | ConvertFrom-Json
    $dependencyDir = Join-Path $bundleRoot 'dependencies'
    New-Item -ItemType Directory -Force -Path $dependencyDir | Out-Null
    $library = Join-Path $dependencyDir 'libpagerctl.so'
    $validLibrary = (Test-Path -LiteralPath $library) -and ((Get-HackomonSha256 $library) -eq $manifest.sha256)
    if (-not $validLibrary) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $manifest.url -OutFile $library }
        catch { throw 'Nao consegui baixar a biblioteca de tela. Confira a Internet do PC e tente novamente.' }
    }
    if ((Get-HackomonSha256 $library) -ne $manifest.sha256) {
        throw 'A biblioteca baixada nao passou na verificacao de integridade. Nada enviado ao Pager.'
    }
    $archive = Join-Path $dependencyDir ('setup-' + [Guid]::NewGuid().ToString('N') + '.tar')
    & $tar.Source -cf $archive -C $bundleRoot payload themes tools dependencies/libpagerctl.so
    if ($LASTEXITCODE -ne 0) { throw 'Nao consegui preparar o pacote. Extraia-o para uma pasta local gravavel e tente novamente.' }
    Write-Host '[3/3] Enviando e instalando...'
    Write-Host 'Quando solicitado, digite a senha do Pager. Os caracteres ficam invisiveis.'
    Write-Host 'Na primeira conexao, confira a identidade do seu Pager antes de aceitar.'
    $result = Send-HackomonArchive -Archive $archive -PagerAddress $PagerAddress -Destination '/mmc/root/hackomon-setup-0.8.7' -SshPath $ssh.Source -SkipTheme:$SkipTheme
    if ($result -eq 3) {
        Write-Host 'APP INSTALADO. O tema ficou pendente; leia o motivo acima.' -ForegroundColor Yellow
        Write-Host 'Voce ja pode abrir Payloads > Games > Hackomon. Detalhes em COMECE_AQUI.md.'
        exit 3
    }
    if ($result -ne 0) { throw "A instalacao parou (codigo $result). Confira a mensagem acima. Se a senha/conexao falhou, abra INSTALAR.cmd novamente. Save e configuracao sao preservados." }
    Write-Host ''
    Write-Host 'PRONTO! App instalado.' -ForegroundColor Green
    if (-not $SkipTheme) { Write-Host 'Tema: Settings > General > Theme > hackomon-field.' }
    Write-Host 'App: Payloads > Games > Hackomon.'
    Write-Host 'Faca uma acao de cuidado, saia com B e abra novamente para conferir o save.'
    exit 0
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 2
}
finally {
    # A single known temporary file inside this bundle; no recursive cleanup.
    if ($archive -and (Test-Path -LiteralPath $archive)) { Remove-Item -LiteralPath $archive -Force }
}
