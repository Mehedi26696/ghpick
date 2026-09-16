from __future__ import annotations

from pathlib import Path

from rich.progress import BarColumn, DownloadColumn, Progress, TaskProgressColumn, TextColumn

from ghpick.github.client import GitHubClient, RepositoryFile
from ghpick.utils.filesystem import ensure_directory, safe_destination


class FileDownloader:
    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    def download_files(self, files: list[RepositoryFile], output_root: Path) -> list[Path]:
        ensure_directory(output_root)
        written: list[Path] = []

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TaskProgressColumn(),
        ) as progress:
            for file in files:
                destination = safe_destination(output_root, file.path)
                ensure_directory(destination.parent)
                task = progress.add_task(file.name, total=file.size or None)
                response = self.client.download(file.download_url)
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        progress.update(task, advance=len(chunk))
                progress.update(task, completed=file.size or None)
                written.append(destination)

        return written

    def download_single_file(self, file: RepositoryFile, output_root: Path) -> Path:
        ensure_directory(output_root)
        destination = safe_destination(output_root, file.name)
        ensure_directory(destination.parent)

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(file.name, total=file.size or None)
            response = self.client.download(file.download_url)
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    progress.update(task, advance=len(chunk))
            progress.update(task, completed=file.size or None)

        return destination
