import type { TaskRecord } from "./types.js";

export interface DependencyAnalysis {
  cycles: string[][];
  cycle_members: Set<string>;
  missing_dependencies: Map<string, string[]>;
}

function canonicalCycle(cycle: string[]): string[] {
  const body = cycle.slice(0, -1);
  if (body.length === 0) return cycle;
  let best = body;
  for (let index = 1; index < body.length; index += 1) {
    const rotated = [...body.slice(index), ...body.slice(0, index)];
    if (rotated.join("\u0000") < best.join("\u0000")) best = rotated;
  }
  return [...best, best[0]!];
}

export function analyzeDependencies(tasks: TaskRecord[]): DependencyAnalysis {
  const byId = new Map(tasks.map((task) => [task.id, task]));
  const missingDependencies = new Map<string, string[]>();
  for (const task of tasks) {
    const missing = task.dependencies.filter((dependency) => !byId.has(dependency));
    if (missing.length > 0) missingDependencies.set(task.id, [...new Set(missing)].sort());
  }

  const color = new Map<string, "visiting" | "visited">();
  const stack: string[] = [];
  const cycles = new Map<string, string[]>();

  const visit = (id: string): void => {
    color.set(id, "visiting");
    stack.push(id);
    const dependencies = [...(byId.get(id)?.dependencies ?? [])].sort();
    for (const dependency of dependencies) {
      if (!byId.has(dependency)) continue;
      const state = color.get(dependency);
      if (state === "visiting") {
        const start = stack.lastIndexOf(dependency);
        const cycle = canonicalCycle([...stack.slice(start), dependency]);
        cycles.set(cycle.join("->"), cycle);
      } else if (state !== "visited") {
        visit(dependency);
      }
    }
    stack.pop();
    color.set(id, "visited");
  };

  for (const id of [...byId.keys()].sort()) {
    if (!color.has(id)) visit(id);
  }

  const cycleList = [...cycles.values()].sort((left, right) => left.join("->").localeCompare(right.join("->")));
  return {
    cycles: cycleList,
    cycle_members: new Set(cycleList.flatMap((cycle) => cycle.slice(0, -1))),
    missing_dependencies: missingDependencies,
  };
}
