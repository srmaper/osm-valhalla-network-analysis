param(
  [Parameter(Position = 0)][string]$Pbf = '',
  [switch]$BuildOnly,
  [switch]$Check
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$root = Split-Path -Parent $PSScriptRoot
Write-Host "项目目录: $root"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  Write-Host '缺少 WSL。请先安装: https://learn.microsoft.com/windows/wsl/install' -ForegroundColor Red
  exit 1
}

if (-not $Pbf) {
  $candidate = Get-ChildItem -LiteralPath (Join-Path $root 'data\input') -Filter '*.osm.pbf' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($candidate) {
    $Pbf = $candidate.FullName
    Write-Host "未指定 OSM 文件，使用: $($candidate.Name)"
  } elseif (-not $Check) {
    Write-Host '请输入 OSM 文件路径（可直接把 .osm.pbf 拖进窗口），或 Geofabrik 下载链接：'
    $Pbf = (Read-Host 'OSM 文件/链接').Trim().Trim('"')
  }
}

$winRoot = $root -replace '\\', '/'
$wslRoot = (& wsl.exe wslpath -a $winRoot 2>$null)
if (-not $wslRoot) {
  Write-Host '无法在 WSL 中解析项目路径，请确认 WSL 可访问该磁盘。' -ForegroundColor Red
  exit 1
}
$wslRoot = $wslRoot.Trim()

$argList = @()
if ($Check) { $argList += '--check' }
if ($Pbf) {
  if ($Pbf -match '^https?://') {
    $argList += $Pbf
  } else {
    $resolved = (Resolve-Path -LiteralPath $Pbf -ErrorAction SilentlyContinue)
    if (-not $resolved) {
      Write-Host "找不到 OSM 文件: $Pbf" -ForegroundColor Red
      exit 1
    }
    $argList += (& wsl.exe wslpath -a ($resolved.Path -replace '\\', '/')).Trim()
  }
}
if ($BuildOnly) { $argList += '--build-only' }

Write-Host ''
& wsl.exe -u root -- bash "$wslRoot/scripts/oneclick.sh" @argList
$code = $LASTEXITCODE
if ($code -ne 0) {
  Write-Host ''
  Write-Host "处理失败（退出码 $code）。请查看上面的错误信息。" -ForegroundColor Red
  Write-Host '可先运行本文件的 -Check：  一键处理.bat -Check'
}
exit $code
