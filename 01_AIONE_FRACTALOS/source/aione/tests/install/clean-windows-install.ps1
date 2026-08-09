param(
  [string]$SourcePath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$TargetPath = "C:\Dev\AIONE-CleanInstallTest",
  [switch]$Reset,
  [int]$Port = 4325
)

$ErrorActionPreference = "Stop"

function Fail-CleanInstall {
  param([string]$Code, [string]$Message, [int]$ExitCode)
  Write-Error "$Code $Message"
  exit $ExitCode
}

$source = (Resolve-Path -LiteralPath $SourcePath).Path
$targetParent = Split-Path -Parent $TargetPath
if (-not (Test-Path -LiteralPath $targetParent)) {
  New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
}
$targetFull = [System.IO.Path]::GetFullPath($TargetPath)
$allowedRoot = [System.IO.Path]::GetFullPath("C:\Dev")
if (-not $targetFull.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  Fail-CleanInstall "AIONE-CLEAN-INSTALL-UNSAFE-TARGET" "Target must stay under C:\Dev for this destructive test: $targetFull" 30
}

if ((Test-Path -LiteralPath $targetFull) -and -not $Reset) {
  Fail-CleanInstall "AIONE-CLEAN-INSTALL-TARGET-EXISTS" "Target exists. Re-run with -Reset to replace only this test copy." 31
}

if (Test-Path -LiteralPath $targetFull) {
  Remove-Item -LiteralPath $targetFull -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $targetFull | Out-Null

Write-Host "Clean install source: $source"
Write-Host "Clean install target: $targetFull"

$robocopyArgs = @(
  $source,
  $targetFull,
  "/E",
  "/XD", ".git", ".agents", "node_modules", "dist", "build", "publish", ".vite", ".cache", "logs", "tmp", "temp",
  (Join-Path $source ".aione\state"),
  (Join-Path $source ".aione\evidence"),
  (Join-Path $source ".aione\launch"),
  (Join-Path $source ".aione\tasks"),
  (Join-Path $source ".aione\checkpoints"),
  "/XF", "*.log", "*.tmp", "*.temp", "*.bak", "*.orig", "*.rej"
)
robocopy @robocopyArgs | Out-Host
if ($LASTEXITCODE -gt 7) {
  Fail-CleanInstall "AIONE-CLEAN-INSTALL-COPY-FAILED" "robocopy failed with exit code $LASTEXITCODE" 32
}

if (-not (Test-Path -LiteralPath (Join-Path $targetFull "package.json"))) {
  Fail-CleanInstall "AIONE-CLEAN-INSTALL-PACKAGE-MISSING" "Copied target has no package.json." 33
}
if (-not (Test-Path -LiteralPath (Join-Path $targetFull "package-lock.json"))) {
  Fail-CleanInstall "AIONE-CLEAN-INSTALL-LOCKFILE-MISSING" "Copied target has no package-lock.json." 34
}

Push-Location $targetFull
try {
  & ".\INSTALL_AIONE.ps1" -Port $Port
  if ($LASTEXITCODE -ne 0) {
    Fail-CleanInstall "AIONE-CLEAN-INSTALL-INSTALLER-FAILED" "INSTALL_AIONE.ps1 failed in clean target." 35
  }
  & ".\START_AIONE.ps1" -Port $Port
  if ($LASTEXITCODE -ne 0) {
    Fail-CleanInstall "AIONE-CLEAN-INSTALL-START-FAILED" "START_AIONE.ps1 failed in clean target." 36
  }
  & ".\STATUS_AIONE.ps1" -Port $Port
  if ($LASTEXITCODE -ne 0) {
    Fail-CleanInstall "AIONE-CLEAN-INSTALL-STATUS-FAILED" "STATUS_AIONE.ps1 failed in clean target." 37
  }
} finally {
  & ".\STOP_AIONE.ps1" | Out-Host
  Pop-Location
}

Write-Host "AIONE clean Windows install OK"
Write-Host "Target kept for inspection: $targetFull"
exit 0
