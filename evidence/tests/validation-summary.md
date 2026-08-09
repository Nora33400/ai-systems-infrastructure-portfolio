# Release Validation Summary

Validation date: 2026-08-09  
Scope: portfolio copies only; original projects were not changed.

## Public and CI-reproducible checks

| Suite | Exact release result | Record |
| --- | --- | --- |
| AIONE Python | **103 passed, 0 failed, 0 skipped** | [record](aione-python-release.txt) |
| AIONE selected Node.js | **85 passed, 0 failed, 0 skipped** | [record](aione-node-release.txt) |
| FractalOS Python | **149 passed, 0 unexpected failures, 1 expected failure** | [record](fractalos-python-release.txt) |
| Opti curated TypeScript slice | **68 passed, 0 failed, 3 skipped** | [record](opti-public-slice-release.txt) |
| Flow/recovery integration | **1 passed, 0 failed, 0 skipped** | [record](flow-recovery-release.txt) |
| ERA Binary reference runtime | **15 passed, 0 failed, 2 skipped** | [record](era-binary-release.txt) |
| Selected prototypes | **41/41 Python files parsed; 5/5 smoke cases passed** | [record](prototype-release.txt) |

Aggregate executable result: **426 passed, 0 unexpected failures, 5 skipped, 1 expected failure**. The 41 syntax parses are reported separately.

## Why tests do not run

- The FractalOS expected failure preserves a known prototype defect: imported completed-job state is not merged as the test requires. The assertion still runs and is not treated as a pass.
- Two Opti skips require a real Ollama endpoint; baseline CI does not require a model service.
- One Opti skip protects the integrity of a historical receipt whose source hash necessarily changed during mandatory public redaction. Schema and other receipt validations still run.
- Two ERA Binary skips require an optional local signed-model report and a C++ toolchain/runtime path not guaranteed by baseline CI.

## Historical negative evidence

The earlier `fractalos-python-tests.txt` and `opti-tests.txt` show the pre-hardening failure state. They remain available so the release records do not erase the history of the defect and redaction-induced hash mismatches.

## Hardware/model-dependent evidence

The local model benchmark and thermal-abort artifacts were not rerun during feature freeze. Their retained measurements are single-machine evidence with the original sample limits; they are not CI prerequisites or multi-node/HPC validation.
