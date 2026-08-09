from typing import Iterable

def compress_lines(lines: Iterable[str], limit: int = 8) -> str:
    cleaned = [line.strip() for line in lines if line and line.strip()]
    return " | ".join(cleaned[:limit]) + (" | ..." if len(cleaned) > limit else "")
