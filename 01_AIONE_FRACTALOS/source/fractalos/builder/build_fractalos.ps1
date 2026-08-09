$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Staging FractalOS ISO tree..."
python -m fractal_os stage-iso

Write-Host "Attempting ISO build..."
python -m fractal_os build-iso

Write-Host "Done."
