# Adaptive Causal Decomposition

The number of iterations is **not fixed at five**. Five is only a default heuristic.

For a global task (T), Forge determines an appropriate (N) from:

- global complexity;
- required contextual locality;
- dependency depth;
- expected outputs;
- verification scope;
- uncertainty.

## Core invariant

```text
Global task
   ↓
logical + causal + temporal decomposition
   ↓
N localities / child tasks
   ↓
each leaf = exactly one realizable iteration
   ↓
verification
   ↓
causal composition
   ↓
parent result
```

The decomposition is successful only if **every leaf can actually be completed in one iteration/sprint**.

## N is adaptive

```text
Simple task        → N = 1
Moderate task      → N = 2/3/...
Complex task       → N = 5/...
Very complex task  → N may be 8, 13, ... or another justified value
```

The number is chosen from the structure of the problem, not imposed for symmetry.

A child must never be created merely to reach a target number.

## Causal-temporal decomposition

Children should represent meaningful localities of the global task and preserve causal relationships.

If:

```text
A → B → C
```

then Forge should normally execute:

```text
Iteration A
    ↓ produces required state/output
Iteration B
    ↓ produces required state/output
Iteration C
```

Independent branches may execute in parallel only when they have no unresolved causal dependency and do not share mutable workspace state.

## Leaf contract

Every leaf iteration must have:

1. one bounded objective;
2. bounded inputs;
3. a defined output;
4. explicit dependencies;
5. acceptance criteria;
6. verification within the iteration;
7. no hidden work requiring another iteration.

If a supposed leaf is still too complex, it is **not a leaf**: Forge recursively decomposes it again.

## Recursive rule

```text
Can T be completed in one iteration?
        │
     ┌──┴──┐
    YES    NO
     │      │
   LEAF     ↓
          determine N
             ↓
       causal decomposition
             ↓
       T1 ... Tn
             ↓
       test each Ti
        ↙         ↘
    feasible    too complex
       ↓             ↓
    execute      decompose again
```

## Composition

The parent task becomes complete only when the required child iterations are accepted, verified, and their outputs compose into the parent's acceptance criteria.

Completed iterations remain immutable and addressable. If new information changes the plan, Forge replans only the unfinished frontier rather than rewriting completed history.
