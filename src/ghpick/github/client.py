from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

import requests

from ghpick.exceptions import GitHubApiError, GitHubRateLimitError


API_ROOT = "https://api.github.com"
TOKEN_ENV_VARS = (
    "GITHUB_ACCESS_TOKEN",
)


@dataclass(frozen=True)
class RepositoryFile:
    path: str
    name: str
    size: int
    download_url: str


@dataclass(frozen=True)
class RepositoryItem:
    path: str
    name: str
    type: Literal["file", "dir"]
    size: int
    download_url: str | None = None


@dataclass(frozen=True)
class RateLimitSnapshot:
    limit: int | None
    used: int | None
    remaining: int | None
    reset: int | None


class GitHubClient:
    def __init__(self, token: str | None = None, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.token = token or _get_token_from_env()
        self.last_rate_limit: RateLimitSnapshot | None = None
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "GHPick/0.1",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def get_contents(self, owner: str, repo: str, path: str, ref: str) -> Any:
        url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}".rstrip("/")
        response = self._get(url, params={"ref": ref}, timeout=30)
        self._record_rate_limit(response)
        if response.status_code >= 400:
            self._raise_api_error(response)
        return response.json()

    def list_files(self, owner: str, repo: str, path: str, ref: str) -> list[RepositoryFile]:
        contents = self.get_contents(owner, repo, path, ref)
        return self._collect_files(owner, repo, contents, ref)

    def list_tree_files(self, owner: str, repo: str, path: str, ref: str) -> list[RepositoryFile]:
        url = f"{API_ROOT}/repos/{owner}/{repo}/git/trees/{quote(ref, safe='')}"
        response = self._get(url, params={"recursive": "1"}, timeout=30)
        self._record_rate_limit(response)
        if response.status_code >= 400:
            self._raise_api_error(response)

        prefix = path.strip("/")
        files: list[RepositoryFile] = []
        for item in response.json().get("tree", []):
            item_path = item.get("path", "")
            if item.get("type") != "blob":
                continue
            if prefix and item_path != prefix and not item_path.startswith(f"{prefix}/"):
                continue
            files.append(
                RepositoryFile(
                    path=item_path,
                    name=item_path.split("/")[-1],
                    size=int(item.get("size") or 0),
                    download_url=_raw_url(owner, repo, ref, item_path),
                )
            )
        return files

    def list_directory(self, owner: str, repo: str, path: str, ref: str) -> list[RepositoryItem]:
        contents = self.get_contents(owner, repo, path, ref)
        if isinstance(contents, dict):
            contents = [contents]
        items = [
            RepositoryItem(
                path=item["path"],
                name=item["name"],
                type=item["type"],
                size=int(item.get("size") or 0),
                download_url=item.get("download_url"),
            )
            for item in contents
            if item.get("type") in {"file", "dir"}
        ]
        return sorted(items, key=lambda item: (item.type != "dir", item.name.lower()))

    def get_default_branch(self, owner: str, repo: str) -> str:
        response = self._get(f"{API_ROOT}/repos/{owner}/{repo}", timeout=30)
        self._record_rate_limit(response)
        if response.status_code >= 400:
            self._raise_api_error(response)
        default_branch = response.json().get("default_branch")
        if not default_branch:
            raise GitHubApiError(f"Could not determine default branch for {owner}/{repo}.")
        return default_branch

    def download(self, url: str) -> requests.Response:
        response = self._get(url, stream=True, timeout=60)
        if response.status_code >= 400:
            self._raise_api_error(response)
        return response

    def rate_limit(self) -> dict[str, Any]:
        response = self._get(f"{API_ROOT}/rate_limit", timeout=30)
        self._record_rate_limit(response)
        if response.status_code >= 400:
            self._raise_api_error(response)
        return response.json()

    def _get(self, url: str, **kwargs: Any) -> requests.Response:
        try:
            return self.session.get(url, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise GitHubApiError(f"Network error while contacting GitHub: {exc}") from exc

    def _record_rate_limit(self, response: requests.Response) -> None:
        snapshot = _rate_limit_from_headers(response.headers)
        if snapshot:
            self.last_rate_limit = snapshot

    def _collect_files(
        self, owner: str, repo: str, contents: Any, ref: str
    ) -> list[RepositoryFile]:
        if isinstance(contents, dict):
            content_type = contents.get("type")
            if content_type == "file":
                download_url = contents.get("download_url")
                if not download_url:
                    raise GitHubApiError(f"No download URL for {contents.get('path')}.")
                return [
                    RepositoryFile(
                        path=contents["path"],
                        name=contents["name"],
                        size=int(contents.get("size") or 0),
                        download_url=download_url,
                    )
                ]
            if content_type == "dir":
                contents = self.get_contents(owner, repo, contents["path"], ref)
            else:
                return []

        files: list[RepositoryFile] = []
        for item in contents:
            content_type = item.get("type")
            if content_type == "file":
                download_url = item.get("download_url")
                if download_url:
                    files.append(
                        RepositoryFile(
                            path=item["path"],
                            name=item["name"],
                            size=int(item.get("size") or 0),
                            download_url=download_url,
                        )
                    )
            elif content_type == "dir":
                nested = self.get_contents(owner, repo, item["path"], ref)
                files.extend(self._collect_files(owner, repo, nested, ref))
        return files

    def _raise_api_error(self, response: requests.Response) -> None:
        message = f"GitHub API request failed with status {response.status_code}."
        github_message = ""
        try:
            payload = response.json()
            github_message = payload.get("message", "")
            if github_message:
                message = f"{message} {github_message}"
        except ValueError:
            if response.text:
                message = f"{message} {response.text[:200]}"

        if _is_rate_limit_response(response, github_message):
            message = (
                "GitHub API limit reached. Set one of "
                f"{', '.join(TOKEN_ENV_VARS)} for a higher limit."
            )
            raise GitHubRateLimitError(message)
        raise GitHubApiError(message)


def _get_token_from_env() -> str | None:
    for name in TOKEN_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return None


def _rate_limit_from_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> RateLimitSnapshot | None:
    keys = ("X-RateLimit-Limit", "X-RateLimit-Used", "X-RateLimit-Remaining", "X-RateLimit-Reset")
    if not any(headers.get(key) for key in keys):
        return None
    return RateLimitSnapshot(
        limit=_optional_int(headers.get("X-RateLimit-Limit")),
        used=_optional_int(headers.get("X-RateLimit-Used")),
        remaining=_optional_int(headers.get("X-RateLimit-Remaining")),
        reset=_optional_int(headers.get("X-RateLimit-Reset")),
    )


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_rate_limit_response(response: requests.Response, github_message: str = "") -> bool:
    if response.status_code != 403:
        return False
    if response.headers.get("X-RateLimit-Remaining") == "0":
        return True
    return "rate limit" in github_message.lower()


def _raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{owner}/{repo}/"
        f"{quote(ref, safe='')}/{quote(path, safe='/')}"
    )
