from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist", ".cache", "cache", "weights"}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".gguf", ".safetensors", ".iso", ".zip", ".7z", ".sqlite", ".sqlite3", ".db", ".pyc", ".o", ".elf"}
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
TOKEN_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]


def tracked_files() -> list[Path]:
    return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and ".release_work" not in p.parts]


def check_layout(files: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_dir() and path.name in FORBIDDEN_DIRS and path.name != ".git":
            issues.append(f"forbidden directory: {path.relative_to(ROOT)}")
    for path in files:
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name.startswith(".env"):
            issues.append(f"forbidden file: {path.relative_to(ROOT)}")
    qemu = sorted((ROOT / "01_AIONE_FRACTALOS" / "evidence" / "qemu").glob("*.log"))
    if len(qemu) != 4:
        issues.append(f"expected 4 QEMU evidence logs, found {len(qemu)}")
    return issues


def check_python(files: list[Path]) -> tuple[int, list[str]]:
    issues: list[str] = []
    count = 0
    for path in files:
        if path.suffix != ".py":
            continue
        count += 1
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            issues.append(f"python syntax: {path.relative_to(ROOT)}: {exc}")
    return count, issues


def check_links(files: list[Path]) -> tuple[int, list[str]]:
    checked = 0
    issues: list[str] = []
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8-sig")
        for match in LINK_RE.finditer(text):
            raw = match.group(1).strip()
            if raw.startswith(("http://", "https://", "mailto:", "data:", "#")):
                continue
            target = raw.strip("<>").split("#", 1)[0].strip()
            target = re.sub(r"\s+[\"'][^\"']+[\"']$", "", target)
            if not target:
                continue
            checked += 1
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.exists():
                issues.append(f"missing link: {path.relative_to(ROOT)} -> {raw}")
    return checked, issues


def check_content(files: list[Path]) -> list[str]:
    issues: list[str] = []
    user_root = "C:" + "\\" + "Users" + "\\"
    private_key = "BEGIN " + "PRIVATE KEY"
    for path in files:
        if path == Path(__file__).resolve() or path.suffix.lower() not in {".md", ".txt", ".log", ".json", ".yaml", ".yml", ".py", ".mjs", ".js", ".ts", ".ps1", ".c", ".h", ".toml", ""}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            continue
        if user_root.lower() in text.lower() or "C:/Users/".lower() in text.lower():
            issues.append(f"absolute user path: {path.relative_to(ROOT)}")
        if private_key in text:
            issues.append(f"private-key marker: {path.relative_to(ROOT)}")
        if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
            issues.append(f"known token form: {path.relative_to(ROOT)}")
    return issues


def main() -> int:
    files = tracked_files()
    issues = check_layout(files)
    python_count, python_issues = check_python(files)
    link_count, link_issues = check_links(files)
    issues.extend(python_issues)
    issues.extend(link_issues)
    issues.extend(check_content(files))
    print(f"files={len(files)} python_parsed={python_count} local_links_checked={link_count} issues={len(issues)}")
    for issue in issues:
        print(f"ERROR: {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

