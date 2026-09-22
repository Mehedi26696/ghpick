import requests

from ghpick.exceptions import GitHubApiError, GitHubRateLimitError
from ghpick.github.client import GitHubClient, _is_rate_limit_response, _rate_limit_from_headers


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}

    def get(self, *args, **kwargs):
        return self.response


def make_json_response(payload, status_code=200, headers=None):
    response = requests.Response()
    response.status_code = status_code
    response._content = __import__("json").dumps(payload).encode("utf-8")
    if headers:
        response.headers.update(headers)
    return response


def test_client_reads_github_access_token(monkeypatch):
    monkeypatch.delenv("GITHUB_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_ACCESS_TOKEN", "secret-token")

    session = requests.Session()
    GitHubClient(session=session)

    assert session.headers["Authorization"] == "Bearer secret-token"


def test_explicit_token_overrides_env(monkeypatch):
    monkeypatch.setenv("GITHUB_ACCESS_TOKEN", "env-token")

    session = requests.Session()
    GitHubClient(token="explicit-token", session=session)

    assert session.headers["Authorization"] == "Bearer explicit-token"


def test_rate_limit_snapshot_from_headers():
    headers = requests.structures.CaseInsensitiveDict(
        {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Used": "12",
            "X-RateLimit-Remaining": "4988",
            "X-RateLimit-Reset": "1790000000",
        }
    )

    snapshot = _rate_limit_from_headers(headers)

    assert snapshot is not None
    assert snapshot.limit == 5000
    assert snapshot.used == 12
    assert snapshot.remaining == 4988
    assert snapshot.reset == 1790000000


def test_rate_limit_snapshot_ignores_missing_headers():
    assert _rate_limit_from_headers(requests.structures.CaseInsensitiveDict()) is None


def test_detects_rate_limit_from_headers():
    response = requests.Response()
    response.status_code = 403
    response.headers["X-RateLimit-Remaining"] = "0"

    assert _is_rate_limit_response(response)


def test_detects_rate_limit_from_message():
    response = requests.Response()
    response.status_code = 403

    assert _is_rate_limit_response(response, "API rate limit exceeded")


def test_raise_api_error_uses_typed_rate_limit_error():
    response = requests.Response()
    response.status_code = 403
    response.headers["X-RateLimit-Remaining"] = "0"
    response._content = b'{"message": "API rate limit exceeded"}'

    client = GitHubClient(token="token")

    try:
        client._raise_api_error(response)
    except GitHubRateLimitError as exc:
        assert "GitHub API limit reached" in str(exc)
    else:
        raise AssertionError("Expected GitHubRateLimitError")


def test_raise_api_error_keeps_non_rate_limit_403_generic():
    response = requests.Response()
    response.status_code = 403
    response._content = b'{"message": "Resource not accessible"}'

    client = GitHubClient(token="token")

    try:
        client._raise_api_error(response)
    except GitHubApiError as exc:
        assert type(exc) is GitHubApiError
    else:
        raise AssertionError("Expected GitHubApiError")


def test_list_directory_sorts_directories_first():
    response = make_json_response(
        [
            {
                "path": "README.md",
                "name": "README.md",
                "type": "file",
                "size": 13,
                "download_url": "https://example.com/README.md",
            },
            {
                "path": "src",
                "name": "src",
                "type": "dir",
                "size": 0,
                "download_url": None,
            },
        ]
    )
    client = GitHubClient(session=FakeSession(response))

    items = client.list_directory("user", "repo", "", "main")

    assert [item.name for item in items] == ["src", "README.md"]
    assert items[0].type == "dir"


def test_get_default_branch():
    response = make_json_response({"default_branch": "main"})
    client = GitHubClient(session=FakeSession(response))

    assert client.get_default_branch("user", "repo") == "main"
