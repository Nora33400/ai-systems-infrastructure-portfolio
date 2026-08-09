const RAW_REASONING_KEYS = new Set(["chainOfThought", "rawChainOfThought", "rawThought", "hiddenReasoning"]);

function clone(value) {
  return structuredClone(value);
}

function rejectRawReasoning(value, path = "record") {
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    if (RAW_REASONING_KEYS.has(key)) throw new Error(`Mémoire réflexive refusée: ${path}.${key}`);
    rejectRawReasoning(item, `${path}.${key}`);
  }
}

class ReflectionMemory {
  #entries = [];
  #maximumEntries;

  constructor({ maximumEntries = 1000 } = {}) {
    this.#maximumEntries = Math.max(10, Number(maximumEntries) || 1000);
  }

  append(record) {
    rejectRawReasoning(record);
    const entry = Object.freeze({ ...clone(record), recordedAt: record.recordedAt || new Date().toISOString() });
    this.#entries.push(entry);
    if (this.#entries.length > this.#maximumEntries) this.#entries.splice(0, this.#entries.length - this.#maximumEntries);
    return clone(entry);
  }

  recordPrediction({ subject, predicted, actual, unit = "score", evidence = [] }) {
    return this.append({
      type: "PREDICTION_ERROR",
      subject: String(subject),
      predicted: Number(predicted),
      actual: Number(actual),
      absoluteError: Math.abs(Number(actual) - Number(predicted)),
      unit: String(unit),
      evidence: evidence.map(String)
    });
  }

  list() {
    return this.#entries.map(clone);
  }
}

export { ReflectionMemory, rejectRawReasoning };
