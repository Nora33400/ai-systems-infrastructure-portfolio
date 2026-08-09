param(
    [string]$Kernel = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$IsoRoot = Join-Path $Root "build\\iso_root"
$LimineRoot = Join-Path $Root "tooling\\limine"

if (-not $Kernel) {
    $Kernel = Join-Path $Root "build\\fractal_kernel.elf"
}

if (-not (Test-Path $Kernel)) {
    throw "Kernel not found: $Kernel"
}

if (-not (Test-Path $LimineRoot)) {
    throw "Limine tooling not found. Run .\\fetch_limine.ps1 first."
}

New-Item -ItemType Directory -Force -Path $IsoRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $IsoRoot "boot") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $IsoRoot "boot\\limine") | Out-Null

Copy-Item $Kernel (Join-Path $IsoRoot "boot\\fractal_kernel.elf") -Force
Copy-Item (Join-Path $Root "limine\\limine.conf") (Join-Path $IsoRoot "boot\\limine\\limine.conf") -Force

$candidateFiles = @(
    "limine-bios.sys",
    "limine-bios-cd.bin",
    "limine-uefi-cd.bin",
    "BOOTIA32.EFI",
    "BOOTX64.EFI"
)

foreach ($name in $candidateFiles) {
    $match = Get-ChildItem -Path $LimineRoot -Recurse -Filter $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($match) {
        Copy-Item $match.FullName (Join-Path $IsoRoot "boot\\limine\\$name") -Force
    }
}

Write-Host "Staged ISO root at $IsoRoot"
