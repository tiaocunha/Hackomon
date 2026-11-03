param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*$')][string]$PagerAddress = '172.16.52.1')
$ErrorActionPreference = 'Stop'
$process = $null
try {
    $ssh = @(Get-Command ssh.exe -CommandType Application -ErrorAction SilentlyContinue)[0]
    if (-not $ssh) { throw 'Cliente OpenSSH do Windows ausente.' }
    Write-Host 'Diagnostico: deixe o Hackomon fechado e mantenha o Pager conectado ao PC.'
    Write-Host 'Informe a senha do Pager quando solicitado. Nenhum radio sera reconfigurado.'
    $script = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot 'diagnose_radios.py'))
    $command = 'export PATH=/mmc/usr/bin:/mmc/usr/sbin:$PATH; export LD_LIBRARY_PATH=/mmc/usr/lib:/mmc/lib:$LD_LIBRARY_PATH; exec python3 -'
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $ssh.Source
    $info.Arguments = '-o ConnectTimeout=8 -o ConnectionAttempts=1 root@' + $PagerAddress + ' "' + $command + '"'
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) { throw 'Nao consegui abrir a conexao.' }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($script)
    $process.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $process.StandardInput.Close()
    $report = $process.StandardOutput.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0 -or -not $report.Contains('HACKOMON - DIAGNOSTICO DE RADIOS')) { throw 'O diagnostico nao terminou. Confira a conexao, senha e Python instalado.' }
    $output = Join-Path (Split-Path -Parent $PSScriptRoot) 'DIAGNOSTICO-HACKOMON.txt'
    [System.IO.File]::WriteAllText($output, $report, [System.Text.UTF8Encoding]::new($false))
    Write-Host $report
    Write-Host "Relatorio salvo: $output" -ForegroundColor Green
    exit 0
}
catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 2 }
finally { if ($process) { $process.Dispose() } }
