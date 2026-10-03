# Contextual Locality

Forge treats context locality as a progressive expansion model: start with the smallest useful unit and expand only when the task requires more meaning.

## Locality ladder

`L0 letter → L1 word → L2 sentence → L3 paragraph → L4 paragraph series → L5 short file → L6 medium file → L7 long file`

A paragraph series may contain **2, 4, or more paragraphs** when the meaning crosses paragraph boundaries.

## Selection algorithm

1. Identify the current subtask and its acceptance criterion.
2. Start at the smallest locality that can satisfy it.
3. If meaning is insufficient, expand one level.
4. Record the selected locality and stable source reference in the checkpoint.
5. Verify using the smallest sufficient locality.
6. Contract back to a narrower locality for the next action when possible.

### Example

```text
Need one symbol       → letter
Need lexical meaning → word
Need local syntax     → sentence
Need argument/idea    → paragraph
Need multi-paragraph reasoning → paragraph series (2/4/+)
Need file-level structure → short/medium/long file
```

## Why this belongs in long-horizon planning

A long task should not automatically hydrate every iteration with the complete repository or complete conversation. Each iteration references the root mission while loading only the relevant contextual locality.

`Context(iteration) = RootSummary + ActiveConstraints + DependencyOutputs + LatestCheckpoint + RelevantArtifacts@required_locality`

This reduces unnecessary context load while preserving traceability.

## Stable references

Where possible, locality references should preserve:

- file/artifact identifier;
- section or heading;
- paragraph/sentence/offset span;
- parent iteration/task identifier;
- plan version.

Expanding locality must not silently merge unrelated text. When broader context is required, the checkpoint records why it expanded.

## Relationship with decomposition

Context locality and recursive task decomposition are complementary:

`complex task → decomposed iterations → smallest sufficient context per iteration`

A subtask that is executable in one iteration should receive enough context to succeed, but not an automatic dump of all parent history.

Security and human-approval rules always take precedence over locality selection.
