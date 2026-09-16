import pytest

from ghpick.exceptions import InvalidGitHubUrlError
from ghpick.github.parser import parse_github_repo_url, parse_github_url


def test_parse_folder_url():
    target = parse_github_url("https://github.com/user/repo/tree/main/backend/api")

    assert target.owner == "user"
    assert target.repo == "repo"
    assert target.ref == "main"
    assert target.path == "backend/api"
    assert target.kind == "directory"
    assert target.basename == "api"


def test_parse_file_url():
    target = parse_github_url("https://github.com/user/repo/blob/dev/model.py")

    assert target.owner == "user"
    assert target.repo == "repo"
    assert target.ref == "dev"
    assert target.path == "model.py"
    assert target.kind == "file"


def test_rejects_non_github_url():
    with pytest.raises(InvalidGitHubUrlError):
        parse_github_url("https://example.com/user/repo/tree/main/backend")


def test_rejects_repository_home_url():
    with pytest.raises(InvalidGitHubUrlError):
        parse_github_url("https://github.com/user/repo")


def test_parse_repository_url_for_browser():
    reference = parse_github_repo_url("https://github.com/user/repo")

    assert reference.owner == "user"
    assert reference.repo == "repo"
    assert reference.ref is None
    assert reference.path == ""


def test_parse_tree_url_for_browser_start_path():
    reference = parse_github_repo_url("https://github.com/user/repo/tree/dev/backend/api")

    assert reference.owner == "user"
    assert reference.repo == "repo"
    assert reference.ref == "dev"
    assert reference.path == "backend/api"
