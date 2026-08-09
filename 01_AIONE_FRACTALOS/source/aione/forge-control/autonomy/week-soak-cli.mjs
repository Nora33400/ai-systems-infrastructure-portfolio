import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { WeekSoakAnalyzer } from "./week-soak-analyzer.mjs";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const configPath = join(projectRoot, "config", "week-soak-production.json");
const production = JSON.parse(readFileSync(configPath, "utf8"));
const analyzer = new WeekSoakAnalyzer({
  rootDir: process.env.AIONE_RUNTIME_DIR
    ? join(resolve(process.env.AIONE_RUNTIME_DIR), "WeekSoak")
    : production.runtimeRoot,
  config: {
    sampleIntervalMs: Number(production.sampleIntervalMinutes || 5) * 60 * 1000,
    maxSamples: Number(production.maximumSamples || 2_304),
    criteria: {
      minCoverageRatio: Number(production.successGates?.minimumSampleCoverage ?? 0.95),
      minForgeHealthyRatio: Number(production.successGates?.minimumForgeAvailability ?? 0.99),
      maxCriticalErrors: Number(production.successGates?.maximumCriticalIncidentsOpenAtEnd ?? 0),
      maxCanonicalMutations: Number(production.successGates?.maximumCanonicalMutationsWithoutOwner ?? 0)
    }
  }
});

const command = String(process.argv[2] || "status").toLowerCase();
const result = command === "status"
  ? analyzer.getStatus()
  : command === "report"
    ? { status: analyzer.getStatus(), report: analyzer.readFinalReport() }
    : null;

if (!result) {
  process.stderr.write("Usage: node week-soak-cli.mjs <status|report>\n");
  process.exitCode = 2;
} else {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}
