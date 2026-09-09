param(
    [string]$UnityEditor = 'C:\Program Files\Unity\Hub\Editor\6000.6.0f1\Editor\Unity.exe',
    [switch]$SkipBuild,
    [switch]$UseOpenEditor,
    [switch]$Rebuild,
    [string]$UnityCli = 'C:\Program Files\Unity Hub\resources\cli\unity.exe'
)
$ErrorActionPreference = 'Stop'
$twRoot = Split-Path -Parent $PSScriptRoot
$twProject = Join-Path $twRoot 'demo\TextureWorksMaterialLab'
if ($UseOpenEditor) {
    New-Item -ItemType Directory -Path (Join-Path $twProject 'Evidence') -Force | Out-Null
    function Invoke-TwLabCommand {
        param([string[]]$CommandArgs)
        $twRaw = (& $UnityCli command @CommandArgs --project-path $twProject --timeout 420 --json) -join [Environment]::NewLine
        if ($LASTEXITCODE -ne 0) { throw "Unity CLI failed: $($CommandArgs[0]); $twRaw" }
        $twResponse = $twRaw | ConvertFrom-Json
        if (-not $twResponse.success -or $twResponse.data.success -eq $false) {
            throw "Unity command failed: $($CommandArgs[0]); $twRaw"
        }
        return $twResponse.data.result
    }
    function Wait-TwLabState {
        param([bool]$Playing)
        $twDeadline = [DateTime]::UtcNow.AddSeconds(60)
        $twStableReads = 0
        do {
            # Domain reload briefly disconnects Pipeline. Retry only this read;
            # never retry a failed validation or a scene/build mutation.
            $twRaw = (& $UnityCli command lab_ready --project-path $twProject --timeout 10 --json) -join [Environment]::NewLine
            $twResponse = $twRaw | ConvertFrom-Json
            if ($twResponse.success) {
                $twState = $twResponse.data.result
                if ($twState.ready -and $twState.playing -eq $Playing) { $twStableReads++ }
                else { $twStableReads = 0 }
                if ($twStableReads -ge 5) { return }
            } elseif ($twRaw -notmatch 'Network error|connect|timed out|timeout') {
                throw "Cannot read editor readiness: $twRaw"
            }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $twDeadline)
        throw "Editor did not become ready (playing=$Playing): $twRaw"
    }
    Invoke-TwLabCommand -CommandArgs @('editor_stop') | Out-Null
    Wait-TwLabState -Playing $false
    if ($Rebuild) {
        Invoke-TwLabCommand -CommandArgs @('cluster_rebuild') | Out-Null
        Wait-TwLabState -Playing $false
    } else {
        $twScenes = Invoke-TwLabCommand -CommandArgs @('list_open_scenes')
        if ($twScenes.scenes | Where-Object { $_.isDirty }) {
            throw 'Preserve unsaved scene edits before validation, or use -Rebuild to save backup copies and regenerate.'
        }
        Invoke-TwLabCommand -CommandArgs @('open_scene', '--path', 'Assets/TextureWorks/Scenes/MaterialLab.unity') | Out-Null
    }
    if (-not $SkipBuild) {
        $twBuild = Invoke-TwLabCommand -CommandArgs @('lab_build_windows')
        $twBuild | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $twProject 'Evidence\player-build.json') -Encoding utf8
    }
    try {
        Invoke-TwLabCommand -CommandArgs @('editor_play') | Out-Null
        Wait-TwLabState -Playing $true
        $twLab = Invoke-TwLabCommand -CommandArgs @('lab_validate')
        $twCluster = Invoke-TwLabCommand -CommandArgs @('cluster_validate')
        Write-Output "Lab checks: $($twLab.checks.Count); cluster checks: $($twCluster.checks)"
        Write-Output "Reports: $twProject\Evidence"
    } finally {
        Invoke-TwLabCommand -CommandArgs @('editor_stop') | Out-Null
        Wait-TwLabState -Playing $false
    }
    return
}
if ($Rebuild) { throw '-Rebuild requires -UseOpenEditor. The ordinary batch path validates the committed scene.' }
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
