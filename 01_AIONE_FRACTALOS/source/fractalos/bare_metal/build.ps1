param(
    [string]$Cc = "",
    [string]$Ld = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Root "build"
New-Item -ItemType Directory -Force -Path $Build | Out-Null

function Require-Tool($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required tool not found: $Name. Install a cross compiler before building the real kernel."
    }
}

if (-not $Cc) {
    if (Get-Command x86_64-elf-gcc -ErrorAction SilentlyContinue) {
        $Cc = "x86_64-elf-gcc"
    } elseif (Get-Command clang -ErrorAction SilentlyContinue) {
        $Cc = "clang"
    } elseif (Test-Path "C:\Program Files\LLVM\bin\clang.exe") {
        $Cc = "C:\Program Files\LLVM\bin\clang.exe"
    } else {
        throw "No kernel compiler found. Install LLVM or x86_64-elf-gcc."
    }
}

if (-not $Ld) {
    if (Get-Command x86_64-elf-ld -ErrorAction SilentlyContinue) {
        $Ld = "x86_64-elf-ld"
    } elseif (Get-Command ld.lld -ErrorAction SilentlyContinue) {
        $Ld = "ld.lld"
    } elseif (Test-Path "C:\Program Files\LLVM\bin\ld.lld.exe") {
        $Ld = "C:\Program Files\LLVM\bin\ld.lld.exe"
    } else {
        throw "No kernel linker found. Install LLVM/lld or x86_64-elf-ld."
    }
}

Require-Tool $Cc
Require-Tool $Ld

$Include = Join-Path $Root "kernel\include"
$CFlags = @("-target", "x86_64-unknown-none", "-std=c11", "-ffreestanding", "-fno-stack-protector", "-fno-stack-check", "-fno-lto", "-fno-pic", "-m64", "-march=x86-64", "-mcmodel=kernel", "-mno-red-zone", "-mgeneral-regs-only", "-mno-mmx", "-mno-sse", "-mno-sse2", "-Wall", "-Wextra", "-O2", "-I$Include")
if ($Cc -like "*x86_64-elf-gcc*") {
    $CFlags = @("-std=c11", "-ffreestanding", "-fno-stack-protector", "-fno-stack-check", "-fno-lto", "-fno-pic", "-m64", "-march=x86-64", "-mcmodel=kernel", "-mno-red-zone", "-mgeneral-regs-only", "-mno-mmx", "-mno-sse", "-mno-sse2", "-Wall", "-Wextra", "-O2", "-I$Include")
}
$Sources = @(
    @{ In = "kernel\boot.S"; Out = "boot.o" },
    @{ In = "kernel\fractal_kernel.c"; Out = "fractal_kernel.o" },
    @{ In = "kernel\arch\x86_64\serial.c"; Out = "serial.o" },
    @{ In = "kernel\arch\x86_64\gdt.c"; Out = "gdt.o" },
    @{ In = "kernel\arch\x86_64\idt.c"; Out = "idt.o" },
    @{ In = "kernel\arch\x86_64\pic.c"; Out = "pic.o" },
    @{ In = "kernel\arch\x86_64\keyboard.c"; Out = "keyboard.o"; Extra = @("-mgeneral-regs-only") },
    @{ In = "kernel\arch\x86_64\timer.c"; Out = "timer.o"; Extra = @("-mgeneral-regs-only") },
    @{ In = "kernel\core\syscall.c"; Out = "syscall.o"; Extra = @("-mgeneral-regs-only") },
    @{ In = "kernel\core\console.c"; Out = "console.o" },
    @{ In = "kernel\core\task.c"; Out = "task.o" },
    @{ In = "kernel\core\userspace.c"; Out = "userspace.o" },
    @{ In = "kernel\core\regime.c"; Out = "regime.o" },
    @{ In = "kernel\core\semantic_memory.c"; Out = "semantic_memory.o" },
    @{ In = "kernel\core\universe.c"; Out = "universe.o" },
    @{ In = "kernel\core\illusion.c"; Out = "illusion.o" },
    @{ In = "kernel\core\foundry.c"; Out = "foundry.o" },
    @{ In = "kernel\core\proofstate.c"; Out = "proofstate.o" },
    @{ In = "kernel\core\desktop_plane.c"; Out = "desktop_plane.o" },
    @{ In = "kernel\core\scientific_formula.c"; Out = "scientific_formula.o" },
    @{ In = "kernel\core\vfs.c"; Out = "vfs.o" },
    @{ In = "kernel\core\package.c"; Out = "package.o" },
    @{ In = "kernel\core\storage_plane.c"; Out = "storage_plane.o" },
    @{ In = "kernel\core\pmm.c"; Out = "pmm.o" },
    @{ In = "kernel\core\heap.c"; Out = "heap.o" },
    @{ In = "kernel\core\slab.c"; Out = "slab.o" },
    @{ In = "kernel\core\vmm.c"; Out = "vmm.o" },
    @{ In = "kernel\core\scheduler.c"; Out = "scheduler.o" },
    @{ In = "kernel\core\triple_kernel.c"; Out = "triple_kernel.o" }
)

$Objects = @()
foreach ($Source in $Sources) {
    $OutPath = Join-Path $Build $Source.Out
    $CompileFlags = @($CFlags)
    if ($Source.ContainsKey("Extra")) {
        $CompileFlags += $Source.Extra
    }
    & $Cc @CompileFlags -c (Join-Path $Root $Source.In) -o $OutPath
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed for $($Source.In)" }
    $Objects += $OutPath
}

& $Ld -nostdlib -static -z max-page-size=0x1000 -T (Join-Path $Root "kernel\linker.ld") @Objects -o (Join-Path $Build "fractal_kernel.elf")
if ($LASTEXITCODE -ne 0) { throw "Link failed for fractal_kernel.elf" }

Write-Host "Built FractalOS kernel: $(Join-Path $Build 'fractal_kernel.elf')"
