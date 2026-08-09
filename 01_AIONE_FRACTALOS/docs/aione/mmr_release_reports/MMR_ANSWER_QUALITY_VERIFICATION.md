# MMR Answer Quality Verification

Benchmark: MMR-ANSWER-QUALITY-VERIFICATION-0001
Source: <AIONE_WORKSPACE>
Strategy: answer_quality_source_verification
Result: verified

## VerifiedAnswer

| Query | Mode | Relative cost | Evidence | Completeness | Unsupported | Contradictions | Missing key points | Quality |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| architecture | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| architecture | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| architecture | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| architecture | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| architecture | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| tests | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| tests | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| tests | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| tests | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| tests | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| erreurs | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| erreurs | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| erreurs | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| erreurs | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| erreurs | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| todo | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| todo | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| todo | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| todo | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| todo | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| fonctions_principales | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| fonctions_principales | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| fonctions_principales | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| fonctions_principales | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| fonctions_principales | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| dependances | naive_full_scan_answer | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 0.856 |
| dependances | mmr_minimal_answer | 0.017 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| dependances | diffcache_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| dependances | bounded_predictive_answer | 0.009 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| dependances | auto_tuned_answer | 0.001 | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |

## SourceVerifier

Each important sentence is checked for chunk citation, unsupported claims, and simple contradiction markers against the selected source chunks.

## CompletenessCheck

Each reduced answer is compared with the naive full-scan answer key points.

## Metrics

Best answer quality score: 1.0
Minimum evidence score: 1.0
Minimum completeness score: 1.0
Unsupported claims: 0
Contradictions: 0

## Internal Engineering Result

In these deterministic project-designed cases, AIONE reduced materialized chunks while keeping answers sourced and complete against its own naive full-scan baseline. This is lexical/internal verification, not independent model-quality or scientific validation.
