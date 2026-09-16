from __future__ import annotations

from fnmatch import fnmatch

from ghpick.github.client import RepositoryFile


def filter_files(
    files: list[RepositoryFile], includes: tuple[str, ...], excludes: tuple[str, ...]
) -> list[RepositoryFile]:
    return [
        file
        for file in files
        if _matches_includes(file, includes) and not _matches_excludes(file, excludes)
    ]


def _matches_includes(file: RepositoryFile, includes: tuple[str, ...]) -> bool:
    if not includes:
        return True
    return any(_matches_pattern(file, pattern) for pattern in includes)


def _matches_excludes(file: RepositoryFile, excludes: tuple[str, ...]) -> bool:
    return any(_matches_pattern(file, pattern) for pattern in excludes)


def _matches_pattern(file: RepositoryFile, pattern: str) -> bool:
    normalized = file.path.replace("\\", "/")
    name = file.name
    segments = normalized.split("/")
    return (
        fnmatch(normalized, pattern)
        or fnmatch(name, pattern)
        or pattern in segments
        or normalized.startswith(pattern.rstrip("/") + "/")
    )
