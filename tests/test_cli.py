from ghpick.cli.commands import (
    _archive_name,
    _dedupe_files,
    _format_reset_time,
    _normalize_file_paths,
    _uses_multiple_repos,
)
from ghpick.github.client import RepositoryFile
from ghpick.github.parser import parse_github_url


def test_format_reset_time_handles_missing_values():
    assert _format_reset_time(None) == "unknown"


def test_format_reset_time_handles_invalid_values():
    assert _format_reset_time("not-a-timestamp") == "unknown"


def test_single_file_url_keeps_basename_for_backward_compatibility():
    target = parse_github_url("https://github.com/user/repo/blob/main/src/model.py")
    files = [RepositoryFile("src/model.py", "model.py", 1, "https://example.com/model.py")]

    normalized = _normalize_file_paths(files, target)

    assert normalized[0].path == "model.py"


def test_multiple_file_targets_keep_repo_paths():
    target = parse_github_url("https://github.com/user/repo/blob/main/src/model.py")
    files = [RepositoryFile("src/model.py", "model.py", 1, "https://example.com/model.py")]

    normalized = _normalize_file_paths(files, target, keep_file_path=True)

    assert normalized[0].path == "src/model.py"


def test_multiple_repos_prefix_paths():
    target = parse_github_url("https://github.com/user/repo/blob/main/src/model.py")
    files = [RepositoryFile("src/model.py", "model.py", 1, "https://example.com/model.py")]

    normalized = _normalize_file_paths(files, target, keep_file_path=True, prefix="user/repo")

    assert normalized[0].path == "user/repo/src/model.py"


def test_archive_name_for_multiple_targets_same_repo():
    targets = [
        parse_github_url("https://github.com/user/repo/blob/main/a.py"),
        parse_github_url("https://github.com/user/repo/tree/main/backend"),
    ]

    assert _archive_name(targets) == "repo-selection.zip"


def test_archive_name_for_multiple_targets_multiple_repos():
    targets = [
        parse_github_url("https://github.com/user/repo/blob/main/a.py"),
        parse_github_url("https://github.com/other/project/blob/main/b.py"),
    ]

    assert _archive_name(targets) == "ghpick-selection.zip"
    assert _uses_multiple_repos(targets)


def test_dedupe_files_by_output_path():
    first = RepositoryFile("src/model.py", "model.py", 1, "https://example.com/1")
    second = RepositoryFile("src/model.py", "model.py", 1, "https://example.com/2")

    assert _dedupe_files([first, second]) == [first]
