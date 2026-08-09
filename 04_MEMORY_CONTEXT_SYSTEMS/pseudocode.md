# Context Reactivation Pseudocode

```text
function reactivate(intent, budget, mode):
    anchors = index.search(intent)
    frontier = priority_queue(anchors)
    selected = []

    while frontier not empty and budget.remaining:
        tile = frontier.pop_best()
        if not verify_hash_and_provenance(tile): continue
        if violates_access_policy(tile): continue
        if marginal_value(tile, selected) <= 0: continue

        selected.append(tile)
        budget.consume(estimated_materialization_cost(tile, mode))
        frontier.add(tile.dependencies)

    context = reconstruct(selected, mode, budget)
    append_usage_event(selected, context.hash)
    refresh_logical_temperatures(selected)
    return context
```

This generalization is P2. The linked thermal tile store implements and tests several of these operations.

