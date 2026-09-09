param(
    [Parameter(Mandatory = $true)][string]$UnityEditor
)
$ErrorActionPreference = 'Stop'
$textureworksRoot = Split-Path -Parent $PSScriptRoot
$textureworksProject = Join-Path ([IO.Path]::GetTempPath()) ('textureworks-parallax-' + [guid]::NewGuid().ToString())
$textureworksAssets = Join-Path $textureworksProject 'Assets\TextureWorks'
$textureworksEditor = (Resolve-Path -LiteralPath $UnityEditor).Path

New-Item -ItemType Directory -Path (Join-Path $textureworksAssets 'Tests\Editor') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $textureworksProject 'Packages') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $textureworksRoot 'unity\TextureWorksParallax.hlsl') -Destination $textureworksAssets
Copy-Item -LiteralPath (Join-Path $textureworksRoot 'tests\unity\ParallaxConformance.shader') -Destination (Join-Path $textureworksAssets 'Tests')
Copy-Item -LiteralPath (Join-Path $textureworksRoot 'tests\unity\ParallaxConformance.cs') -Destination (Join-Path $textureworksAssets 'Tests\Editor')
Copy-Item -LiteralPath (Join-Path $textureworksRoot 'tests\unity\ParallaxGeometry.shader') -Destination (Join-Path $textureworksAssets 'Tests')
Copy-Item -LiteralPath (Join-Path $textureworksRoot 'tests\unity\ParallaxGeometry.cs') -Destination (Join-Path $textureworksAssets 'Tests\Editor')
$textureworksFixtures = Join-Path $textureworksProject 'fixtures'
Push-Location $textureworksRoot
try {
    & (Join-Path $textureworksRoot '.venv\Scripts\python.exe') -m scripts.prepare_parallax_validation --output $textureworksFixtures
    if ($LASTEXITCODE -ne 0) { throw 'POM fixture generation failed' }
} finally { Pop-Location }
Copy-Item -LiteralPath $textureworksFixtures -Destination (Join-Path $textureworksAssets 'Fixtures') -Recurse

# Use the selected editor's bundled SRP package and its matching dependencies.
$textureworksPackages = Join-Path (Split-Path -Parent $textureworksEditor) 'Data\Resources\PackageManager\BuiltInPackages'
$textureworksCore = Get-Content -Raw -LiteralPath (Join-Path $textureworksPackages 'com.unity.render-pipelines.core\package.json') | ConvertFrom-Json
@{ dependencies = @{ 'com.unity.render-pipelines.core' = $textureworksCore.version } } |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $textureworksProject 'Packages\manifest.json') -Encoding utf8

$textureworksLog = Join-Path $textureworksProject 'unity.log'
$textureworksArguments = @('-batchmode', '-force-d3d11', '-projectPath', ('"' + $textureworksProject + '"'),
    '-executeMethod', 'TextureWorksParallaxConformance.Run', '-logFile', ('"' + $textureworksLog + '"'))
Write-Output "Conformance project: $textureworksProject"
$textureworksProcess = Start-Process -FilePath $textureworksEditor -ArgumentList $textureworksArguments -WorkingDirectory $textureworksProject -WindowStyle Hidden -PassThru
Write-Output "Unity PID: $($textureworksProcess.Id)"
Write-Output "Log: $textureworksLog"
# Bounded runtime, including import and license checks. No unattended editor left
# running if compilation prevents the execute method from being reached.
if (-not $textureworksProcess.WaitForExit(300000)) {
    $textureworksProcess.Kill()
    throw "Unity validation timed out. Inspect $textureworksLog"
}
$textureworksResults = Join-Path $textureworksProject 'parallax-results.txt'
if (Test-Path -LiteralPath $textureworksResults) { Get-Content -LiteralPath $textureworksResults }
if ($textureworksProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $textureworksResults)) {
    throw "Unity validation failed. Inspect $textureworksLog"
}
& (Join-Path $textureworksRoot '.venv\Scripts\python.exe') (Join-Path $textureworksRoot 'scripts\summarize_parallax_validation.py') (Join-Path $textureworksProject 'geometry-validation')
if ($LASTEXITCODE -ne 0) { throw 'POM report generation failed' }
Write-Output "Geometry comparison: $(Join-Path $textureworksProject 'geometry-validation')"
