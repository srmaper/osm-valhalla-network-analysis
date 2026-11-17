param(
  [Parameter(Position = 0)][string]$Pbf = '',
  [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  throw 'WSL is required: https://learn.microsoft.com/windows/wsl/install'
}

$winRoot = $root -replace '\\', '/'
$wslRoot = (& wsl.exe wslpath -a $winRoot 2>$null)
if (-not $wslRoot) { throw 'Could not resolve the project path inside WSL' }
$wslRoot = $wslRoot.Trim()

$argList = @()
if ($Pbf) {
  if ($Pbf -match '^https?://') {
    $argList += $Pbf
  } else {
    $resolved = (Resolve-Path -LiteralPath $Pbf).Path
    $argList += (& wsl.exe wslpath -a ($resolved -replace '\\', '/')).Trim()
  }
} else {
  Write-Host 'Usage: 一键处理.bat <region.osm.pbf | geofabrik-url> [-BuildOnly]'
  Write-Host 'Example: 一键处理.bat D:\osm\hong-kong-latest.osm.pbf'
}
if ($BuildOnly) { $argList += '--build-only' }

& wsl.exe -u root -- bash "$wslRoot/scripts/oneclick.sh" @argList
exit $LASTEXITCODE
