#include "era_runtime.hpp"

#include <algorithm>
#include <stdexcept>

namespace aione::era {

Schedule select_morphology(const std::vector<GpuState>& gpus,
                           const double computational_complexity,
                           const double coordination_complexity,
                           const double uncertainty,
                           const SchedulerPolicy& policy) {
  const auto valid_score = [](const double value) { return value >= 0.0 && value <= 1.0; };
  if (!valid_score(computational_complexity) || !valid_score(coordination_complexity) ||
      !valid_score(uncertainty)) {
    throw std::invalid_argument("complexity values must be between zero and one");
  }

  std::vector<const GpuState*> usable;
  for (const auto& gpu : gpus) {
    const auto free_mb = gpu.memory_total_mb > gpu.memory_used_mb
                             ? gpu.memory_total_mb - gpu.memory_used_mb
                             : 0;
    if (gpu.temperature_celsius < policy.thermal_limit_celsius &&
        free_mb >= policy.reserve_vram_mb) {
      usable.push_back(&gpu);
    }
  }

  Schedule result;
  if (usable.size() >= 2 && (computational_complexity + coordination_complexity) / 2.0 >= 0.65) {
    result.morphology = Morphology::MultiGpu;
    result.gpu_uuids = {usable[0]->uuid, usable[1]->uuid};
    result.hypothesis_branches = std::min<std::size_t>(16, 4 + static_cast<std::size_t>(12 * uncertainty));
  } else if (!usable.empty() && computational_complexity >= 0.35) {
    result.morphology = Morphology::CpuGpu;
    result.gpu_uuids = {usable[0]->uuid};
    result.hypothesis_branches = std::min<std::size_t>(8, 2 + static_cast<std::size_t>(6 * uncertainty));
  }
  return result;
}

const char* morphology_name(const Morphology morphology) noexcept {
  switch (morphology) {
    case Morphology::CpuGpu:
      return "CPU_GPU";
    case Morphology::MultiGpu:
      return "MULTI_GPU";
    case Morphology::CpuOnly:
    default:
      return "CPU_ONLY";
  }
}

}  // namespace aione::era
