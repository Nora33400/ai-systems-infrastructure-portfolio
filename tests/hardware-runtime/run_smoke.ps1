param(
  [int]$CpuSeconds = 20,
  [int]$GpuSeconds = 30,
  [int]$MatrixSize = 2048
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$report = Join-Path $PSScriptRoot "runtime-report.json"
$start = Get-Date

function Run-Nvidia([string]$args) {
  $p = Start-Process nvidia-smi -ArgumentList $args -NoNewWindow -PassThru -Wait
  return $p.ExitCode
}

Write-Host "=== Forge hardware runtime smoke test ==="
Write-Host "Target: Ryzen 7 5700X / 32GB DDR4 / RTX 3060 12GB + RTX 4060 8GB"

$cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
$os = Get-CimInstance Win32_OperatingSystem
$memBefore = [math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2)

$gpuRaw = & nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null
$gpuDetected = $LASTEXITCODE -eq 0

$phase = @()
$phase += [pscustomobject]@{name="cpu_ram_baseline"; status=if($cpu){"ok"}else{"fail"}; timestamp=(Get-Date).ToString("o")}

if(-not $gpuDetected) {
  Write-Warning "nvidia-smi unavailable; GPU phases cannot be verified."
} else {
  $phase += [pscustomobject]@{name="gpu_discovery"; status="ok"; timestamp=(Get-Date).ToString("o"); telemetry=$gpuRaw}
}

# CPU/RAM activity: parallel PowerShell workers perform real arithmetic.
$jobs = 1..([Environment]::ProcessorCount/2) | ForEach-Object {
  Start-Job -ScriptBlock {
    param($seconds)
    $until=(Get-Date).AddSeconds($seconds); $x=0.123456789
    while((Get-Date) -lt $until){ $x=[math]::Sqrt(($x*$x)+1.23456789) }
    $x
  } -ArgumentList $CpuSeconds
}
$null=$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job -Force
$os = Get-CimInstance Win32_OperatingSystem
$memAfterCpu = [math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2)
$phase += [pscustomobject]@{name="cpu_ram_load"; status="completed"; ram_used_mb_before=$memBefore; ram_used_mb_after=$memAfterCpu}

# GPU telemetry before/after. Real CUDA inference should be supplied by the local runtime (Ollama/llama.cpp/etc).
# We deliberately do not fabricate CUDA compute from PowerShell.
$gpuAfterCpu = & nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>$null
$phase += [pscustomobject]@{name="gpu_preflight"; status=if($LASTEXITCODE -eq 0){"ok"}else{"fail"}; telemetry=$gpuAfterCpu}

$reportObj=[pscustomobject]@{
  started_at=$start.ToString("o")
  finished_at=(Get-Date).ToString("o")
  host=$cpu
  target=@{ram_gb=32; gpus=@("RTX 3060 12GB","RTX 4060 8GB")}
  phases=$phase
  note="This smoke test validates host/telemetry and CPU activity. For actual dual-GPU inference, run the optional Ollama/local-model phase with one worker pinned per GPU."
}
$reportObj | ConvertTo-Json -Depth 8 | Set-Content $report -Encoding UTF8
Write-Host "Report: $report"
