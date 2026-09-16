from ghpick.filters.file_filter import filter_files
from ghpick.github.client import RepositoryFile


def make_file(path: str, size: int = 10) -> RepositoryFile:
    return RepositoryFile(path=path, name=path.split("/")[-1], size=size, download_url="https://example.com")


def test_include_patterns_match_file_names():
    files = [make_file("backend/api.py"), make_file("backend/config.json")]

    result = filter_files(files, includes=("*.py",), excludes=())

    assert [file.path for file in result] == ["backend/api.py"]


def test_exclude_matches_folder_segments():
    files = [make_file("backend/api.py"), make_file("backend/tests/test_api.py")]

    result = filter_files(files, includes=(), excludes=("tests",))

    assert [file.path for file in result] == ["backend/api.py"]
