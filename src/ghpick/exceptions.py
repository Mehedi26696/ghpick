class GHPickError(Exception):
    """Base exception for user-facing GHPick failures."""


class InvalidGitHubUrlError(GHPickError):
    """Raised when a GitHub URL cannot be parsed as a file or folder target."""


class GitHubApiError(GHPickError):
    """Raised when GitHub returns an error response."""


class GitHubRateLimitError(GitHubApiError):
    """Raised when GitHub reports that the API rate limit is exhausted."""
