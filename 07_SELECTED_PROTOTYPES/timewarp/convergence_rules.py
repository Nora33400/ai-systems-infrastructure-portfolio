
def should_stop(gain: float, epsilon: float, cost: float, budget: float, coherence: float, threshold: float) -> bool:
    return gain < epsilon or cost > budget or coherence >= threshold
