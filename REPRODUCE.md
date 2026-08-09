# Reproduce the Public Evidence

The baseline is designed for a clean checkout without secrets, GPUs, Ollama, external services, or the original private projects.

## Supported environment

- Windows 11 or a recent Linux distribution
- Python 3.12+; the release audit used Python 3.14
- Node.js 24+ for `node:sqlite` and the retained TypeScript tests
- Git 2.40+

## Baseline validation

```bash
python -m pip install pytest
python tools/validate_portfolio.py
node --test 03_FLOW_RECOVERY_SYSTEM/flow_recovery_demo.test.mjs
```

Run the Python suites from their project-copy directories, exactly as CI does. This makes imports independent of any local `PYTHONPATH` value:

```bash
cd 01_AIONE_FRACTALOS/source/aione
python -m pytest tests -q -p no:cacheprovider
cd ../../..

cd 01_AIONE_FRACTALOS/source/fractalos
python -m pytest tests -q -p no:cacheprovider
cd ../../..
```

The FractalOS suite contains one explicit expected failure for the known inherited-job mesh merge defect. It must remain visible in the test summary.

## Selected AIONE Node.js tests

```bash
node tools/run_aione_node_tests.mjs
```

The runner uses the AIONE copy as its working directory and executes the same 12 files in CI and in the release audit.

## ERA Binary reference runtime

```bash
cd 01_AIONE_FRACTALOS/source/aione/forge-control/autonomy/era-binary
python -m unittest discover -s tests -q
```

The two expected skips cover an optional signed local-model report and an optional C++ toolchain path.

## Requirement-to-system TypeScript slice

```bash
cd 05_REQUIREMENT_TO_SYSTEM_PIPELINE/source/opti
npm install --ignore-scripts
npm test
```

This installs only declared JavaScript development dependencies, compiles the retained source/tests, and executes all compiled public tests. Expected skips are the unavailable real Ollama integrations and the pre-redaction WQ-0042 receipt hash assertion. Schema validation for that receipt still runs elsewhere in the same file.

## Prototype smoke checks

```bash
python 07_SELECTED_PROTOTYPES/local_model_router/router.py
python 07_SELECTED_PROTOTYPES/public_innovations/derived-xconcept-autorepair/main.py --test-pass-rate 0.9 --consecutive-fails 2
python 07_SELECTED_PROTOTYPES/public_innovations/xconcept-error-engine/main.py --has-tests --contradictions 1
```

`tools/validate_portfolio.py` parses every tracked Python file without importing hardware or service integrations.

## Local hardware/model evidence

The JSON benchmark artifacts are retained measurements, not automatically rerun by baseline validation. Repeating them requires the recorded NVIDIA hardware, a local Ollama endpoint, and the named model already installed. The repository does not download models or require API credentials. One RTX 4060 report contains four requests at one repetition; one RTX 3060 report records a thermal abort at 82 °C.

## Expected outputs

Release-gate results and exact versions are recorded in [FINAL_PUBLICATION_AUDIT.md](FINAL_PUBLICATION_AUDIT.md). Historical pre-hardening records remain under [`evidence/tests`](evidence/tests/) and are labeled accordingly.
