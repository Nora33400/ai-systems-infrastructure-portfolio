param(
    [string]$Tag = "v11.4.0-binary"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolingRoot = Join-Path $Root "tooling"
$LimineRoot = Join-Path $ToolingRoot "limine"

New-Item -ItemType Directory -Force -Path $ToolingRoot | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required to fetch the official Limine binary branch."
}

if (Test-Path $LimineRoot) {
    Remove-Item -Recurse -Force $LimineRoot
}

git clone https://github.com/Limine-Bootloader/Limine.git --branch=$Tag --depth=1 $LimineRoot
if ($LASTEXITCODE -ne 0) {
    throw "Failed to fetch Limine binary branch $Tag."
}

Write-Host "Fetched Limine into $LimineRoot"
