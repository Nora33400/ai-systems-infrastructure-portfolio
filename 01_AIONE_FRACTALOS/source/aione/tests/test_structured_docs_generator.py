from __future__ import annotations

from pathlib import Path

from scripts.generate_structured_docs import STANDARD_FILES, TOPICS, generate


def test_structured_docs_generator_creates_full_matrix(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    result = generate(docs_root)

    assert result["folders"] == 31
    assert result["standard_files"] == 12
    assert result["written"] == 31 * 12 + 1
    assert (docs_root / "DOCUMENTATION_SYSTEM.md").exists()

    for topic in TOPICS:
        folder = docs_root / topic["folder"]
        assert folder.is_dir()
        for filename in STANDARD_FILES:
            path = folder / filename
            assert path.exists(), str(path)
            text = path.read_text(encoding="utf-8")
            assert "Status actuel" in text
            assert "Preuves dans le depot" in text
            assert "A implementer" in text


def test_structured_docs_generator_dry_run_does_not_write(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    result = generate(docs_root, dry_run=True)

    assert result["dry_run"] is True
    assert result["written"] == 31 * 12 + 1
    assert not docs_root.exists()
