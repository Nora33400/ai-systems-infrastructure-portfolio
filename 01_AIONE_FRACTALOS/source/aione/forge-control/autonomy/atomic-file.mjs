import { renameSync } from "node:fs";

const RETRYABLE = new Set(["EPERM", "EACCES", "EBUSY"]);
const sleeper = new Int32Array(new SharedArrayBuffer(4));

export function renameWithRetry(source, destination, {
  attempts = 21,
  delayMs = 25,
  rename = renameSync,
  wait = (milliseconds) => Atomics.wait(sleeper, 0, 0, milliseconds)
} = {}) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      rename(source, destination);
      return { ok: true, attempts: attempt };
    } catch (error) {
      lastError = error;
      if (!RETRYABLE.has(error?.code) || attempt === attempts) throw error;
      wait(delayMs);
    }
  }
  throw lastError;
}
