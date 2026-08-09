# MMR External Workload Adapter

Benchmark: MMR-EXTERNAL-WORKLOAD-ADAPTER-0001
Source: <AIONE_WORKSPACE>
Strategy: external_workload_adapter
Result: measured

## WorkloadSource

Files: 125
Total bytes: 906052
File types: .json, .md, .py
Source fingerprint: f64afe97acd1bf52097284a652b9b29f09dc6076ad64f40e809efa851c2f0f69

## Runtime Evaluation

| Query | Mode | Total chunks | Materialized | Reused | Rebuilt | Relative cost | Latency ms | Warnings | Coherence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| architecture | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 38.445 | 0 | 1.0 |
| architecture | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 13.384 | 0 | 1.0 |
| architecture | diffcache | 729 | 0 | 8 | 0 | 0.001 | 13.207 | 0 | 1.0 |
| architecture | microdelta | 729 | 0 | 8 | 0 | 0.001 | 13.232 | 0 | 1.0 |
| architecture | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 13.368 | 0 | 1.0 |
| architecture | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 13.207 | 0 | 1.0 |
| tests | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 36.845 | 0 | 1.0 |
| tests | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 11.75 | 0 | 1.0 |
| tests | diffcache | 729 | 0 | 8 | 0 | 0.001 | 11.541 | 0 | 1.0 |
| tests | microdelta | 729 | 0 | 8 | 0 | 0.001 | 11.556 | 0 | 1.0 |
| tests | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 11.686 | 0 | 1.0 |
| tests | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 11.541 | 0 | 1.0 |
| erreurs | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 37.185 | 0 | 1.0 |
| erreurs | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 12.106 | 0 | 1.0 |
| erreurs | diffcache | 729 | 0 | 8 | 0 | 0.001 | 11.897 | 0 | 1.0 |
| erreurs | microdelta | 729 | 0 | 8 | 0 | 0.001 | 11.912 | 0 | 1.0 |
| erreurs | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 12.043 | 0 | 1.0 |
| erreurs | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 11.897 | 0 | 1.0 |
| todo | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 37.104 | 0 | 1.0 |
| todo | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 12.019 | 0 | 1.0 |
| todo | diffcache | 729 | 0 | 8 | 0 | 0.001 | 11.802 | 0 | 1.0 |
| todo | microdelta | 729 | 0 | 8 | 0 | 0.001 | 11.815 | 0 | 1.0 |
| todo | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 11.944 | 0 | 1.0 |
| todo | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 11.802 | 0 | 1.0 |
| fonctions_principales | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 36.742 | 0 | 1.0 |
| fonctions_principales | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 11.677 | 0 | 1.0 |
| fonctions_principales | diffcache | 729 | 0 | 8 | 0 | 0.001 | 11.474 | 0 | 1.0 |
| fonctions_principales | microdelta | 729 | 0 | 8 | 0 | 0.001 | 11.492 | 0 | 1.0 |
| fonctions_principales | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 11.627 | 0 | 1.0 |
| fonctions_principales | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 11.474 | 0 | 1.0 |
| dependances | naive_full_scan | 729 | 729 | 0 | 729 | 1.0 | 37.008 | 0 | 1.0 |
| dependances | mmr_minimal | 729 | 8 | 0 | 8 | 0.017 | 11.925 | 0 | 1.0 |
| dependances | diffcache | 729 | 0 | 8 | 0 | 0.001 | 11.713 | 0 | 1.0 |
| dependances | microdelta | 729 | 0 | 8 | 0 | 0.001 | 11.727 | 0 | 1.0 |
| dependances | bounded_predictive | 729 | 4 | 4 | 4 | 0.009 | 11.858 | 0 | 1.0 |
| dependances | auto_tuned | 729 | 0 | 8 | 0 | 0.001 | 11.713 | 0 | 1.0 |

## Mutations

| Mutation | Total chunks | Materialized | Reused | Rebuilt | Relative cost | Latency ms | Warnings | Coherence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modify_file | 729 | 3 | 5 | 3 | 0.007 | 5.724 | 0 | 1.0 |
| modify_small_chunk | 729 | 0 | 8 | 0 | 0.001 | 5.465 | 0 | 1.0 |
| add_file | 730 | 1 | 7 | 1 | 0.003 | 5.386 | 0 | 1.0 |
| delete_file | 518 | 0 | 8 | 0 | 0.001 | 3.535 | 0 | 1.0 |

## Metrics

Total files: 125
Total chunks: 729
Best relative cost: 0.001
Max reused chunks: 8
Mutation rebuilt chunks: 4
Warning count: 0

## Internal Engineering Result

The MMR runtime indexed the selected local file fixture, answered the project-defined code/document queries with bounded chunk materialization, and preserved reuse under the recorded mutations. This is not an independent workload benchmark.
