# MMR Real User Task Benchmark

Benchmark: MMR-REAL-USER-TASK-BENCHMARK-0001
Source: <AIONE_WORKSPACE>
Strategy: real_user_task_benchmark
Result: measured

## Task Set

- explain_project_architecture: Explain project architecture
- find_feature_location: Find where to add a feature
- identify_mmr_tests: Identify tests related to MMR
- summarize_recent_changes: Summarize recent changes
- locate_technical_risks: Locate technical risks
- propose_next_step: Propose next step
- generate_sourced_mini_report: Generate a sourced mini report

## Task Benchmark

| Task | Mode | Relative cost | Latency ms | Evidence | Completeness | Unsupported | Contradictions | Task success | Source coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| explain_project_architecture | naive_full_scan | 1.0 | 37.812 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| explain_project_architecture | mmr_minimal | 0.017 | 13.071 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| explain_project_architecture | diffcache | 0.001 | 12.868 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| explain_project_architecture | microdelta | 0.001 | 12.889 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| explain_project_architecture | bounded_predictive | 0.009 | 13.025 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| explain_project_architecture | auto_tuned | 0.001 | 12.868 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | naive_full_scan | 1.0 | 37.963 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | mmr_minimal | 0.017 | 13.189 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | diffcache | 0.001 | 12.981 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | microdelta | 0.001 | 12.997 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | bounded_predictive | 0.009 | 13.128 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| find_feature_location | auto_tuned | 0.001 | 12.981 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | naive_full_scan | 1.0 | 36.689 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | mmr_minimal | 0.017 | 11.894 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | diffcache | 0.001 | 11.684 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | microdelta | 0.001 | 11.699 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | bounded_predictive | 0.009 | 11.829 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| identify_mmr_tests | auto_tuned | 0.001 | 11.684 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | naive_full_scan | 1.0 | 37.942 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | mmr_minimal | 0.017 | 13.171 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | diffcache | 0.001 | 12.959 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | microdelta | 0.001 | 12.975 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | bounded_predictive | 0.009 | 13.109 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| summarize_recent_changes | auto_tuned | 0.001 | 12.959 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | naive_full_scan | 1.0 | 37.004 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | mmr_minimal | 0.017 | 12.215 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | diffcache | 0.001 | 12.005 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | microdelta | 0.001 | 12.019 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | bounded_predictive | 0.009 | 12.148 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| locate_technical_risks | auto_tuned | 0.001 | 12.005 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | naive_full_scan | 1.0 | 37.631 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | mmr_minimal | 0.017 | 12.864 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | diffcache | 0.001 | 12.656 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | microdelta | 0.001 | 12.671 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | bounded_predictive | 0.009 | 12.801 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| propose_next_step | auto_tuned | 0.001 | 12.656 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | naive_full_scan | 1.0 | 36.761 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | mmr_minimal | 0.017 | 11.969 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | diffcache | 0.001 | 11.762 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | microdelta | 0.001 | 11.778 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | bounded_predictive | 0.009 | 11.909 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |
| generate_sourced_mini_report | auto_tuned | 0.001 | 11.762 | 1.0 | 1.0 | 0 | 0 | 1.0 | 1.0 |

## Metrics

Average task success score: 1.0
Average source coverage score: 1.0
Best relative cost: 0.001
Average reduced relative cost: 0.006
Minimum evidence score: 1.0
Minimum completeness score: 1.0
Unsupported claims: 0
Contradictions: 0

## Quality Verification

VerifiedAnswer, SourceVerifier and CompletenessCheck are applied per task and per mode.

## Internal Engineering Result

Across seven project-designed developer-agent task types, AIONE preserved its internal source-grounding checks while reducing chunk materialization versus its own full-scan baseline. The tasks and scoring are heuristic and were not independently validated.
