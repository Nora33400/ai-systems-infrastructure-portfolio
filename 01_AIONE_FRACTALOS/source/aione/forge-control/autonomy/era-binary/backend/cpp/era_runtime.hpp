#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace aione::era {

struct GpuState {
  std::string uuid;
  std::uint32_t temperature_celsius{};
  std::uint64_t memory_total_mb{};
  std::uint64_t memory_used_mb{};
};

struct SchedulerPolicy {
  std::uint32_t thermal_limit_celsius{82};
  std::uint64_t reserve_vram_mb{1024};
};

enum class Morphology { CpuOnly, CpuGpu, MultiGpu };

struct Schedule {
  Morphology morphology{Morphology::CpuOnly};
  std::vector<std::string> gpu_uuids;
  std::size_t hypothesis_branches{1};
};

Schedule select_morphology(const std::vector<GpuState>& gpus,
                           double computational_complexity,
                           double coordination_complexity,
                           double uncertainty,
                           const SchedulerPolicy& policy = {});

const char* morphology_name(Morphology morphology) noexcept;

}  // namespace aione::era
