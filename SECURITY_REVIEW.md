# Security and Publication Review

Review date: 2026-08-09  
Scope: files Git would publish from this portfolio copy.

## Findings corrected

- Removed the internal discovery report that exposed local drive and archive topology; replaced it with a public selection/provenance note.
- Replaced personal profile paths, owner identifiers, personal e-mail addresses, and full GPU UUIDs in retained evidence.
- Removed obsolete publication commands and account references from selected prototype documentation.
- Excluded live databases, ledgers, runtime prompts, operational logs, generated builds, archives, caches, virtual environments, worktrees, model weights, and dependency trees.
- Restricted Git's `.log` exception to the four bounded QEMU serial evidence files.

## Contextually reviewed technical strings

- Loopback endpoints are local test fixtures or optional local-model defaults; they identify no external/private service.
- Environment-variable names and synthetic credential-like strings occur in security/refusal tests, but no credential value is stored.
- Technical workspace defaults in copied executable prototypes are not personal profile paths and are not used by the public validation commands.
- Receipt/job identifiers are synthetic or project-scoped evidence correlation identifiers, not authentication or personal-session material.
- Hardware model names and measured temperatures/VRAM are intentionally retained; unique GPU identifiers are redacted.

## License/provenance boundary

No repository-wide open-source license is asserted. [LICENSE](LICENSE) reserves rights and explicitly excludes third-party rights. No third-party dependency tree or binary is vendored; package manifests identify install-time dependencies. The retained material is a curated portfolio copy with the limitations described in [SELECTION_AND_PROVENANCE.md](SELECTION_AND_PROVENANCE.md).

## Residual risk

Automated scans cannot prove the absence of every context-sensitive disclosure. A final human review of the staged diff remains prudent. No known secret, personal identifier, private key, non-placeholder e-mail, personal profile path, hidden runtime dump, archive, database, model weight, cache, or dependency tree remains in the publishable set.
