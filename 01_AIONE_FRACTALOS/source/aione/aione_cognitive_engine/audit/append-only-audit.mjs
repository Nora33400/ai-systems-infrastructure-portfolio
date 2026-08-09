class AppendOnlyAudit {
  #events = [];

  append(event = {}) {
    const previousSequence = this.#events.at(-1)?.sequence || 0;
    const stored = Object.freeze({
      sequence: previousSequence + 1,
      at: event.at || new Date().toISOString(),
      type: String(event.type || "EVENT"),
      decisionId: event.decisionId ? String(event.decisionId) : null,
      summary: String(event.summary || ""),
      evidence: Array.isArray(event.evidence) ? event.evidence.map(String) : []
    });
    this.#events.push(stored);
    return structuredClone(stored);
  }

  list() {
    return this.#events.map((event) => structuredClone(event));
  }
}

export { AppendOnlyAudit };
