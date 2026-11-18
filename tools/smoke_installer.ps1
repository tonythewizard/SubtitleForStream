#requires -Version 7.0
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) {
    throw 'This smoke test installs into a temporary profile on a GitHub Actions runner.'
}

$project = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $project
$version = (Get-Content VERSION -Raw).Trim()
$setup = (Resolve-Path "installer/SubtitleForStream-Setup-$version-x64.exe").Path
$log = Join-Path $project 'installer/smoke-install.log'
$installDir = Join-Path $env:RUNNER_TEMP 'SubtitleForStream-smoke'
$profileDir = Join-Path $env:RUNNER_TEMP 'SubtitleForStream-profile'
$args = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/TASKS=desktopicon',
          ('/DIR="' + $installDir + '"'), ('/LOG="' + $log + '"'))
$setupProcess = Start-Process -FilePath $setup -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
if ($setupProcess.ExitCode -ne 0) { throw "Setup exited with $($setupProcess.ExitCode)" }

$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{823BDCFA-FA02-4B1B-AB05-A0F1944F20A6}_is1'
$registration = Get-ItemProperty -LiteralPath $key
if ($registration.DisplayVersion -ne $version -or $registration.InstallLocation.TrimEnd('\') -ne $installDir) {
    throw 'Unexpected Windows install registration.'
}

$exe = Join-Path $installDir 'SubtitleForStream.exe'
$shortcuts = New-Object -ComObject WScript.Shell
foreach ($folder in 'DesktopDirectory', 'Programs') {
    $link = Join-Path ([Environment]::GetFolderPath($folder)) 'SubtitleForStream.lnk'
    if (-not (Test-Path -LiteralPath $link) -or $shortcuts.CreateShortcut($link).TargetPath -ne $exe) {
        throw "Missing or invalid shortcut in $folder."
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $installDir '_internal/LICENSE'))) {
    throw 'GPL license text is missing from the installed app.'
}

$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = $listener.LocalEndpoint.Port
$listener.Stop()
$env:LOCALAPPDATA = $profileDir
$env:APPDATA = $profileDir
$env:HF_HUB_OFFLINE = '1'
& '.\.venv\Scripts\python.exe' -c "from app.settings import Settings; s=Settings(); s.set('obs_port',$port); s.set('autostart_transcription',False); s.set('check_updates_on_startup',False)"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare isolated settings.' }
$env:PATH = "$env:WINDIR\System32;$env:WINDIR"

$app = Start-Process -FilePath $exe -WorkingDirectory $installDir -PassThru -WindowStyle Hidden
try {
    $responded = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($app.HasExited) { throw "Installed app exited with $($app.ExitCode)" }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/overlay" -TimeoutSec 2
            $responded = $response.StatusCode -eq 200 -and $response.Content -match '<title>SubtitleForStream Overlay</title>'
            if ($responded) { break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $responded) { throw 'Installed overlay did not respond.' }
    Write-Host "Installed SubtitleForStream $version. Windows registration, shortcuts, license and local overlay passed."
} finally {
    if (-not $app.HasExited) {
        [void]$app.CloseMainWindow()
        if (-not $app.WaitForExit(5000)) { Stop-Process -Id $app.Id -Force }
    }
}
