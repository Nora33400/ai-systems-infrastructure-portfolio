import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

export function testRuntimeRoot() {
  const root = resolve(process.env.AIONE_TEST_RUNTIME_ROOT || "S:\\AI_LAB\\Runtime\\Tests");
  mkdirSync(root, { recursive: true });
  return root;
}
