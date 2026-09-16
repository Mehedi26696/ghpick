from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from os import getenv
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from ghpick.cli.browser import RepositoryBrowserApp
from ghpick.downloader.file_downloader import FileDownloader
from ghpick.downloader.zip_creator import create_zip
from ghpick.exceptions import GHPickError, GitHubRateLimitError
from ghpick.filters.file_filter import filter_files
from ghpick.github.client import TOKEN_ENV_VARS, GitHubClient, RateLimitSnapshot, RepositoryFile
from ghpick.github.parser import GitHubTarget, parse_github_repo_url, parse_github_url
from ghpick.utils.filesystem import ensure_directory, human_size


console = Console()
COMMAND_NAMES = {"browse", "download", "rate-limit"}


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Download selected GitHub files and inspect API limits."""


@cli.command()
@click.argument("github_urls", nargs=-1)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Directory where files or archives are saved.",
)
@click.option(
    "--zip/--no-zip",
    "zip_output",
    default=None,
    help="Create a zip archive. Defaults to zip for folders and raw output for files.",
)
@click.option("--list", "list_only", is_flag=True, help="Preview files without downloading.")
@click.option("--include", multiple=True, help='Include matching files, for example "*.py".')
@click.option("--exclude", multiple=True, help='Exclude matching files or folders, for example "tests".')
@click.option("--ref", "ref_override", help="Override the branch, tag, or commit parsed from the URL.")
def download(
    github_urls: tuple[str, ...],
    output: Path,
    zip_output: bool | None,
    list_only: bool,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    ref_override: str | None,
) -> None:
    """Download selected GitHub files or folders."""
    load_dotenv()
    if not github_urls:
        raise click.ClickException("Provide at least one GitHub file or folder URL.")
    try:
        _run_download(github_urls, output, zip_output, list_only, include, exclude, ref_override)
    except GitHubRateLimitError as exc:
        if _configured_token_exists():
            raise click.ClickException(str(exc)) from exc
        token = _prompt_for_token_after_rate_limit()
        if not token:
            raise click.ClickException(str(exc)) from exc
        try:
            _run_download(
                github_urls,
                output,
                zip_output,
                list_only,
                include,
                exclude,
                ref_override,
                token=token,
            )
        except GHPickError as retry_exc:
            raise click.ClickException(str(retry_exc)) from retry_exc
        except ValueError as retry_exc:
            raise click.ClickException(str(retry_exc)) from retry_exc
    except GHPickError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _run_download(
    github_urls: tuple[str, ...],
    output: Path,
    zip_output: bool | None,
    list_only: bool,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    ref_override: str | None,
    token: str | None = None,
) -> None:
    try:
        targets = _parse_targets(github_urls, ref_override)
        _run_download_targets(targets, output, zip_output, list_only, include, exclude, token=token)
    except GitHubRateLimitError:
        raise


def _run_download_targets(
    targets: list[GitHubTarget],
    output: Path,
    zip_output: bool | None,
    list_only: bool,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    token: str | None = None,
) -> None:
    try:
        multiple_targets = len(targets) > 1
        multiple_repos = _uses_multiple_repos(targets)

        client = GitHubClient(token=token)
        with console.status("Scanning repository...", spinner="dots"):
            files = _collect_files(client, targets, multiple_targets, multiple_repos)

        files = filter_files(files, include, exclude)
        files = _dedupe_files(files)

        if not files:
            raise GHPickError("No files matched the requested URL and filters.")

        if list_only:
            _print_file_list(files)
            _print_rate_limit_snapshot(client.last_rate_limit)
            return

        ensure_directory(output)
        should_zip = zip_output if zip_output is not None else multiple_targets or targets[0].kind == "directory"

        if should_zip:
            archive = _download_zip(client, files, targets, output)
            console.print(f"[green]Saved:[/green] {archive}")
        elif len(files) == 1 and targets[0].kind == "file":
            destination = FileDownloader(client).download_single_file(files[0], output)
            console.print(f"[green]Saved:[/green] {destination}")
        else:
            written = FileDownloader(client).download_files(files, output)
            console.print(f"[green]Saved {len(written)} files to:[/green] {output.resolve()}")
        _print_rate_limit_snapshot(client.last_rate_limit)
    except GitHubRateLimitError:
        raise


def _prompt_for_token_after_rate_limit() -> str | None:
    console.print(
        "[yellow]GitHub API limit reached and no usable token was loaded.[/yellow]\n"
        "Paste a GitHub token to retry this command now. It will only be used for this run."
    )
    try:
        token = click.prompt("GitHub token", hide_input=True, default="", show_default=False)
    except (click.Abort, click.ClickException):
        return None
    token = token.strip()
    if not token:
        return None
    console.print("[green]Token received. Retrying...[/green]")
    return token


def _configured_token_exists() -> bool:
    return any(getenv(name) for name in TOKEN_ENV_VARS)


@cli.command("browse")
@click.argument("github_url")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Directory where selected files or archives are saved.",
)
@click.option(
    "--zip/--no-zip",
    "zip_output",
    default=None,
    help="Create a zip archive. Defaults to zip for folders and multiple selections.",
)
@click.option("--ref", "ref_override", help="Branch, tag, or commit to browse.")
def browse(github_url: str, output: Path, zip_output: bool | None, ref_override: str | None) -> None:
    """Browse a repository and choose files or folders interactively."""
    load_dotenv()
    try:
        _run_browse(github_url, output, zip_output, ref_override)
    except GitHubRateLimitError as exc:
        if _configured_token_exists():
            raise click.ClickException(str(exc)) from exc
        token = _prompt_for_token_after_rate_limit()
        if not token:
            raise click.ClickException(str(exc)) from exc
        try:
            _run_browse(github_url, output, zip_output, ref_override, token=token)
        except GHPickError as retry_exc:
            raise click.ClickException(str(retry_exc)) from retry_exc
        except ValueError as retry_exc:
            raise click.ClickException(str(retry_exc)) from retry_exc
    except GHPickError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _run_browse(
    github_url: str,
    output: Path,
    zip_output: bool | None,
    ref_override: str | None,
    token: str | None = None,
) -> None:
    try:
        reference = parse_github_repo_url(github_url)
        client = GitHubClient(token=token)
        ref = ref_override or reference.ref or client.get_default_branch(reference.owner, reference.repo)
        app = RepositoryBrowserApp(
            client=client,
            owner=reference.owner,
            repo=reference.repo,
            ref=ref,
            start_path=reference.path,
        )
        targets = app.run()
        if not targets:
            console.print("[yellow]No files or folders selected.[/yellow]")
            return
        _run_download_targets(targets, output, zip_output, list_only=False, token=token)
    except GitHubRateLimitError:
        raise


@cli.command("rate-limit")
def rate_limit() -> None:
    """Show remaining GitHub API requests for the configured token."""
    load_dotenv()
    try:
        client = GitHubClient()
        data = client.rate_limit()
        _print_rate_limit(data, authenticated=bool(client.token))
    except GHPickError as exc:
        raise click.ClickException(str(exc)) from exc


def main(args: list[str] | None = None) -> None:
    """Console-script entrypoint with backward-compatible URL dispatch."""
    argv = list(sys.argv[1:] if args is None else args)
    if argv and argv[0] not in COMMAND_NAMES and argv[0] not in {"-h", "--help"}:
        argv.insert(0, "download")
    cli.main(args=argv, prog_name="ghpick", standalone_mode=True)


def _parse_targets(github_urls: tuple[str, ...], ref_override: str | None) -> list[GitHubTarget]:
    targets = [parse_github_url(url) for url in github_urls]
    if ref_override:
        targets = [target.with_ref(ref_override) for target in targets]
    return targets


def _collect_files(
    client: GitHubClient,
    targets: list[GitHubTarget],
    multiple_targets: bool,
    multiple_repos: bool,
) -> list[RepositoryFile]:
    files: list[RepositoryFile] = []
    for target in targets:
        target_files = client.list_files(target.owner, target.repo, target.path, target.ref)
        prefix = f"{target.owner}/{target.repo}" if multiple_repos else ""
        files.extend(
            _normalize_file_paths(
                target_files,
                target,
                keep_file_path=multiple_targets,
                prefix=prefix,
            )
        )
    return files


def _normalize_file_paths(
    files: list[RepositoryFile],
    target: GitHubTarget,
    keep_file_path: bool = False,
    prefix: str = "",
) -> list[RepositoryFile]:
    if target.kind == "directory" or keep_file_path:
        return [_with_prefix(file, prefix) for file in files]
    return [
        RepositoryFile(
            path=f"{prefix}/{file.name}" if prefix else file.name,
            name=file.name,
            size=file.size,
            download_url=file.download_url,
        )
        for file in files
    ]


def _with_prefix(file: RepositoryFile, prefix: str) -> RepositoryFile:
    if not prefix:
        return file
    return RepositoryFile(
        path=f"{prefix}/{file.path}",
        name=file.name,
        size=file.size,
        download_url=file.download_url,
    )


def _dedupe_files(files: list[RepositoryFile]) -> list[RepositoryFile]:
    unique: dict[str, RepositoryFile] = {}
    for file in files:
        unique.setdefault(file.path, file)
    return list(unique.values())


def _uses_multiple_repos(targets: list[GitHubTarget]) -> bool:
    return len({(target.owner, target.repo) for target in targets}) > 1


def _download_zip(
    client: GitHubClient, files: list[RepositoryFile], targets: list[GitHubTarget], output: Path
) -> Path:
    archive_name = _archive_name(targets)
    archive_path = output / archive_name

    with tempfile.TemporaryDirectory(prefix="ghpick-") as temporary:
        temp_root = Path(temporary)
        FileDownloader(client).download_files(files, temp_root)
        return create_zip(temp_root, archive_path)


def _archive_name(targets: list[GitHubTarget]) -> str:
    if len(targets) == 1:
        target = targets[0]
        return f"{Path(target.basename).stem}.zip" if target.kind == "file" else f"{target.basename}.zip"
    if not _uses_multiple_repos(targets):
        return f"{targets[0].repo}-selection.zip"
    return "ghpick-selection.zip"


def _print_file_list(files: list[RepositoryFile]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("File")
    table.add_column("Size", justify="right")
    for file in files:
        table.add_row(file.path, human_size(file.size))
    console.print(table)


def _print_rate_limit(data: dict[str, Any], authenticated: bool) -> None:
    resources = data.get("resources", {})
    table = Table(title="GitHub API Rate Limit", show_header=True, header_style="bold")
    table.add_column("Resource")
    table.add_column("Limit", justify="right")
    table.add_column("Used", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Reset")

    for name in ("core", "search", "graphql", "code_search"):
        resource = resources.get(name)
        if not resource:
            continue
        table.add_row(
            name,
            str(resource.get("limit", "unknown")),
            str(resource.get("used", "unknown")),
            str(resource.get("remaining", "unknown")),
            _format_reset_time(resource.get("reset")),
        )

    console.print(f"Authenticated: {'yes' if authenticated else 'no'}")
    console.print(table)


def _print_rate_limit_snapshot(snapshot: RateLimitSnapshot | None) -> None:
    if not snapshot:
        return
    console.print(
        "[cyan]API limit:[/cyan] "
        f"Limit {snapshot.limit if snapshot.limit is not None else 'unknown'} | "
        f"Used {snapshot.used if snapshot.used is not None else 'unknown'} | "
        f"Remaining {snapshot.remaining if snapshot.remaining is not None else 'unknown'} | "
        f"Reset {_format_reset_time(snapshot.reset)}"
    )


def _format_reset_time(timestamp: Any) -> str:
    if not timestamp:
        return "unknown"
    try:
        return datetime.fromtimestamp(int(timestamp)).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except (TypeError, ValueError, OSError):
        return "unknown"
