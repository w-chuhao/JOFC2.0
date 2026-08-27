"""Scan text files for stale symbols or paths after cleanup renames.

Usage:
    python scripts/find_stale_references.py ROOT PATTERN [PATTERN ...]
"""

from __future__ import annotations

import argparse
from pathlib import Path


SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def scan(root: Path, patterns: list[str]) -> int:
    matches = 0
    lowered = [(pattern, pattern.lower()) for pattern in patterns]
    for path in iter_text_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lower_line = line.lower()
            for original, lower_pattern in lowered:
                if lower_pattern in lower_line:
                    print(f"{path}:{line_number}: {original}: {line.strip()}")
                    matches += 1
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Find stale references after cleanup renames.")
    parser.add_argument("root", help="Repository or subdirectory to scan.")
    parser.add_argument("patterns", nargs="+", help="Old symbols, filenames, or paths to find.")
    args = parser.parse_args()
    return 1 if scan(Path(args.root), args.patterns) else 0


if __name__ == "__main__":
    raise SystemExit(main())
