# Repository Hygiene Plan

Audit date: 2026-10-16  
Repository: `Nora33400/ai-systems-infrastructure-portfolio`  
Audit base: `main` at `2bf30b5584b5db76e7e3b45a0dfcf48debfd8f1e`

## Purpose

Make the public portfolio easier to navigate, reproduce, review, and maintain without destroying project history or overstating what has been implemented.

This document records an initial read-only audit and the safe order of work. It is not a claim that every source file has already been manually reviewed or that all tests have just been executed.

## Current snapshot

- Default branch: `main`.
- Recursive Git tree: 857 entries, 726 files and 131 directories; tree response was not truncated.
- Top-level technical structure is already grouped into seven numbered portfolio areas, plus `evidence/`, `docs/`, `tests/`, `tools/`, and `.github/`.
- Existing validation workflow: `.github/workflows/validate.yml`; it runs repository validation, selected Python and Node suites, flow/recovery integration tests, and the curated TypeScript suite.
- The repository already has a strong evidence-first README, portfolio index, reproduction guide, evidence matrix, claim-evidence map, authorship disclosure, provenance note, and security review.
- The repository has several feature branches. Open PR #8 targets `main`; open PR #9 targets PR #8's head branch. They must be reviewed in dependency order, not merged independently or automatically.
- The combined commit-status endpoint returned no status entries for the inspected `main`, PR #8, or PR #9 heads. This does **not** prove that GitHub Actions passed; inspect workflow runs/checks directly before approving a merge.
- The root contains a mixture of curated documentation and standalone attachments, including UUID-named JPEGs, PDFs, and a pasted Markdown file named `Fichier markdown(5).md collé`. These need provenance and relevance classification before any rename or move.
- Existing publication/security audit documents carry their own historical audit dates. Preserve those dates as history; add a new dated review rather than rewriting past findings as if they were current.

## Non-destructive invariants

1. Never delete, rename, overwrite, or move existing files until references, provenance, and recovery are checked.
2. Never merge PRs, push directly to `main`, change permissions, enable external network/MCP/OAuth, or promote unverified code as part of this cleanup.
3. Keep external projects as reference-only unless licensing, security, compatibility, and local-first policy have been reviewed.
4. Preserve authorship/AI-assistance disclosure and clearly distinguish measured evidence, synthetic fixtures, expected failures, hypotheses, and architecture-only material.
5. Run the repository's documented validation commands from a clean checkout; retain full logs and report failures rather than hiding them.
6. Make changes in a dedicated branch and present them for review before promotion.

## Work plan

### P0 — Establish a reliable baseline

- [x] Inspect repository metadata, default branch, tree size, README, portfolio index, evidence matrix, reproduction guide, security review, validation workflow, branches, and open PR metadata.
- [ ] Run the full documented validation suite from a clean checkout and capture the exact environment, commands, exit codes, skips, and expected failures.
- [ ] Inspect recent GitHub Actions runs and branch checks; do not infer a pass from missing status records.
- [ ] Record the exact base SHA and review the complete diff before each promotion.

### P1 — Make the public entry points consistent

- [ ] Cross-check all README/index links against the actual tree.
- [ ] Check that the root README, portfolio index, evidence matrix, claim-evidence map, reproduction guide, and release gate use consistent maturity labels and limitations.
- [ ] Ensure measured results always state hardware, workload, sample size, and whether the data is real, synthetic, or simulated.
- [ ] Ensure all documentation distinguishes implemented/tested behavior from architecture, planned work, and external references.
- [ ] Add a single navigation path for a recruiter or technical reviewer: overview → selected code → tests → retained evidence → limitations.

### P2 — Classify root-level attachments

- [ ] Identify the purpose, source, rights/provenance, and current references for each root-level JPEG, PDF, and pasted Markdown file.
- [ ] Decide per item whether it belongs in a documented `docs/` or `evidence/` location, should remain at root, or should be excluded from the public portfolio.
- [ ] Propose any moves/renames in a separate reviewed diff; do not delete or relocate during discovery.
- [ ] Use descriptive, stable filenames and add a short index for retained research attachments.

### P3 — Branch and pull-request hygiene

- [ ] Review PR #8 against `main`, including every changed file and its tests.
- [ ] Review PR #9 only after establishing its dependency on PR #8 and checking its combined diff against `main`.
- [ ] Check the feature branches for unique work, ancestry, stale divergence, and work not represented by an open PR.
- [ ] Do not delete branches or close PRs as a cosmetic cleanup. Make each disposition only after its contents are accounted for.
- [ ] Require successful applicable checks and explicit human review before any merge.

### P4 — Reproducibility and release quality

- [ ] Execute `python tools/validate_portfolio.py`.
- [ ] Execute the exact test commands in `REPRODUCE.md`, including the flow/recovery test and selected Python, Node, ERA, and TypeScript suites.
- [ ] Preserve documented expected failures/skips; investigate any new failure.
- [ ] Verify links and public-file privacy/provenance again after edits.
- [ ] Update the release gate and change manifest with actual results and the final reviewed diff.

## Definition of done

The repository is ready for a cleanup release only when:

- the clean-checkout validation commands have been executed and their real outcomes recorded;
- all public navigation links resolve;
- root attachments have documented dispositions and no unreviewed destructive moves;
- open PRs and branches have a recorded, evidence-based disposition;
- claims in public-facing documents match the implementation and retained evidence;
- provenance, authorship/AI assistance, licensing boundaries, and limitations remain explicit;
- the final diff is reviewed and reversible;
- no merge or release is performed without explicit human approval.

## Initial audit limitations

This first pass inspected repository metadata, the recursive file tree, main navigation and evidence documents, the validation workflow, and open PR metadata. It did not execute code, inspect all 726 files individually, run the CI suite, perform a complete secret scan, or approve/merge any PR. Those are explicit next steps, not assumed results.
