$ErrorActionPreference = "Stop"

$clang = Get-Command clang -ErrorAction SilentlyContinue
$lld = Get-Command lld-link -ErrorAction SilentlyContinue

if (-not $clang -or -not $lld) {
    Write-Error "clang and lld-link are required to build BOOTX64.EFI. They are not installed in this environment."
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $build | Out-Null

$src = Join-Path $root "FractalBootX64.c"
$obj = Join-Path $build "FractalBootX64.obj"
$efi = Join-Path $build "BOOTX64.EFI"

& $clang.Source -target x86_64-pc-win32-coff -ffreestanding -fno-stack-protector -fshort-wchar -mno-red-zone -c $src -o $obj
& $lld.Source /subsystem:efi_application /nodefaultlib /entry:efi_main /out:$efi $obj

Write-Host "Built $efi"
