# Windows PowerShell 5.1 compatible. Binary data never passes through a text pipe.
function Get-HackomonSha256 {
    param([string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Test-HackomonConnection {
    param([string]$PagerAddress)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect($PagerAddress, 22, $null, $null)
        try {
            if (-not $pending.AsyncWaitHandle.WaitOne(4000)) { return $false }
            $client.EndConnect($pending)
            return $true
        }
        finally { $pending.AsyncWaitHandle.Close() }
    }
    catch { return $false }
    finally { $client.Close() }
}

function Send-HackomonArchive {
    param(
        [string]$Archive,
        [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]*$')][string]$PagerAddress,
        [ValidatePattern('^/mmc/root/hackomon-setup-[0-9.]+$')][string]$Destination,
        [string]$SshPath,
        [switch]$SkipTheme
    )
    # All remote command fragments are fixed or validated above. No password is read/stored here.
    $remoteCommand = "set -eu; umask 077; mkdir -p '$Destination'; tar -xf - -C '$Destination'; sh '$Destination/tools/setup_pager.sh' --deps"
    if ($SkipTheme) { $remoteCommand += ' --skip-theme' }
    $remoteCommand += ' </dev/null'
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $SshPath
    $info.Arguments = '-o ConnectTimeout=8 -o ConnectionAttempts=1 root@' + $PagerAddress + ' "' + $remoteCommand + '"'
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    # Keep stdout/stderr and the console attached: OpenSSH handles authentication itself.
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    $inputFile = $null
    $transferError = $null
    try {
        $inputFile = [System.IO.File]::OpenRead($Archive)
        if (-not $process.Start()) { throw 'Nao foi possivel iniciar a conexao SSH.' }
        try {
            $inputFile.CopyTo($process.StandardInput.BaseStream)
            $process.StandardInput.Close()
        }
        catch {
            $transferError = $_
            try { $process.StandardInput.Close() } catch {}
        }
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { return $process.ExitCode }
        if ($transferError) { throw 'A transferencia terminou incompleta. Execute INSTALAR.cmd novamente.' }
        return 0
    }
    finally {
        if ($inputFile) { $inputFile.Dispose() }
        $process.Dispose()
    }
}
