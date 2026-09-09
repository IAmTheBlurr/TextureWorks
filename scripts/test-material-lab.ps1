param(
    [string]$UnityEditor = 'C:\Program Files\Unity\Hub\Editor\6000.6.0f1\Editor\Unity.exe',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$twRoot = Split-Path -Parent $PSScriptRoot
$twProject = Join-Path $twRoot 'demo\TextureWorksMaterialLab'
$twEditorPath = (Resolve-Path -LiteralPath $UnityEditor).Path
$twLog = Join-Path $twProject 'Logs\lab-validation.log'
New-Item -ItemType Directory -Path (Split-Path -Parent $twLog) -Force | Out-Null
$twArgs = @('-batchmode', '-force-d3d11', '-projectPath', ('"' + $twProject + '"'),
    '-executeMethod', 'TextureWorks.MaterialLab.Editor.LabValidation.RunBatch',
    '-logFile', ('"' + $twLog + '"'))
if ($SkipBuild) { $twArgs += '-twSkipBuild' }
$twProcess = Start-Process -FilePath $twEditorPath -ArgumentList $twArgs -WorkingDirectory $twProject -WindowStyle Hidden -PassThru
Write-Output "Unity PID: $($twProcess.Id); log: $twLog"
if (-not $twProcess.WaitForExit(600000)) {
    $twProcess.Kill()
    throw "Lab validation timed out. Inspect $twLog"
}
if ($twProcess.ExitCode -ne 0 -or -not (Select-String -LiteralPath $twLog -Pattern 'TEXTUREWORKS_LAB_VALIDATION_PASSED' -Quiet)) {
    throw "Lab validation failed. Inspect $twLog"
}
Get-Content -LiteralPath (Join-Path $twProject 'Evidence\validation.json')
