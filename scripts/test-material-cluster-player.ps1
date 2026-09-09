param(
    [ValidateSet('d3d11','d3d12')][string]$GraphicsApi = 'd3d11'
)
$ErrorActionPreference = 'Stop'
$twRoot = Split-Path -Parent $PSScriptRoot
$twProject = Join-Path $twRoot 'demo\TextureWorksMaterialLab'
$twBuild = Join-Path $twProject 'Builds\Windows'
$twExe = (Resolve-Path -LiteralPath (Join-Path $twBuild 'TextureWorksMaterialLab.exe')).Path
$twStarted = [DateTime]::UtcNow
# This acceptance run needs a visible backbuffer; a hidden Windows player cannot
# establish screenshot acceptance. The opt-in probe exits when its work finishes.
$twPlayer = Start-Process -FilePath $twExe -WorkingDirectory $twBuild -PassThru -ArgumentList @(
    '-textureworks-smoke', "-force-$GraphicsApi", '-screen-fullscreen', '0',
    '-screen-width', '1440', '-screen-height', '900', '-logFile', 'player-smoke.log')
while (-not $twPlayer.WaitForExit(1000)) {
    if (([DateTime]::UtcNow - $twStarted).TotalSeconds -gt 180) {
        $twPlayer.Kill()
        throw "Player acceptance timed out. Inspect $twBuild\player-smoke.log"
    }
}
$twReportPath = Join-Path $twBuild 'player-smoke.json'
if ($twPlayer.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $twReportPath) -or
    (Get-Item -LiteralPath $twReportPath).LastWriteTimeUtc -lt $twStarted) {
    throw "Player failed or did not write a current report. Inspect $twBuild\player-smoke.log"
}
$twReport = Get-Content -LiteralPath $twReportPath -Raw | ConvertFrom-Json
if (-not $twReport.success -or $twReport.errors.Count -ne 0) { throw 'Player smoke reported runtime errors.' }
$twDestination = Join-Path $twProject "Evidence\cluster\player-$GraphicsApi"
New-Item -ItemType Directory -Path $twDestination -Force | Out-Null
Get-ChildItem -LiteralPath $twBuild -File -Filter 'player-*' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $twDestination -Force
}
Get-Content -LiteralPath $twReportPath
Write-Output "Captures and measured frame timings: $twDestination"
