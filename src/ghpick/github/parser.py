from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlparse

from ghpick.exceptions import InvalidGitHubUrlError


TargetKind = Literal["file", "directory"]


@dataclass(frozen=True)
class GitHubTarget:
    owner: str
    repo: str
    ref: str
    path: str
    kind: TargetKind

    @property
    def basename(self) -> str:
        clean_path = self.path.strip("/")
        if clean_path:
            return clean_path.split("/")[-1]
        return self.repo

    def with_ref(self, ref: str) -> "GitHubTarget":
        return replace(self, ref=ref)


@dataclass(frozen=True)
class GitHubRepoReference:
    owner: str
    repo: str
    ref: str | None = None
    path: str = ""


def parse_github_url(url: str) -> GitHubTarget:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")
        host = parsed.netloc.lower()

    if host not in {"github.com", "www.github.com"}:
        raise InvalidGitHubUrlError("Expected a github.com URL.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 4:
        raise InvalidGitHubUrlError(
            "Expected a GitHub file or folder URL like "
            "https://github.com/owner/repo/tree/main/path."
        )

    owner, repo, route = parts[0], parts[1].removesuffix(".git"), parts[2]
    if route not in {"tree", "blob"}:
        raise InvalidGitHubUrlError("URL must contain /tree/ for folders or /blob/ for files.")

    ref = parts[3]
    path = "/".join(parts[4:])
    kind: TargetKind = "directory" if route == "tree" else "file"

    if kind == "file" and not path:
        raise InvalidGitHubUrlError("File URLs must include a file path after the branch.")

    return GitHubTarget(owner=owner, repo=repo, ref=ref, path=path, kind=kind)


def parse_github_repo_url(url: str) -> GitHubRepoReference:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")
        host = parsed.netloc.lower()

    if host not in {"github.com", "www.github.com"}:
        raise InvalidGitHubUrlError("Expected a github.com URL.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise InvalidGitHubUrlError("Expected a GitHub repository URL like https://github.com/owner/repo.")

    owner, repo = parts[0], parts[1].removesuffix(".git")
    if len(parts) == 2:
        return GitHubRepoReference(owner=owner, repo=repo)

    route = parts[2]
    if route not in {"tree", "blob"} or len(parts) < 4:
        raise InvalidGitHubUrlError(
            "Expected a repository URL or a GitHub tree/blob URL."
        )

    return GitHubRepoReference(
        owner=owner,
        repo=repo,
        ref=parts[3],
        path="/".join(parts[4:]),
    )
