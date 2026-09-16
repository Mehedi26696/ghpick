# GHPick — Selective GitHub File & Folder Downloader

**Download exactly what you need from any public GitHub repository, without cloning the entire thing.**

GHPick is a developer-focused CLI tool that lets you download specific files or folders from public GitHub repositories. Point it at a GitHub URL, and it pulls down only the content you asked for — preserving the original directory structure and optionally bundling everything into a zip archive.

## The Problem

Developers constantly browse GitHub for reference code — ML model implementations, backend examples, algorithm solutions, documentation, config files. But GitHub gives you only two download options: **clone the entire repository** or **download a full zip**.

| Current Approach | What's Wrong |
|---|---|
| `git clone` | Downloads the entire history and every file in the repo |
| GitHub "Download ZIP" | Still downloads the whole repository as a zip |
| `git sparse-checkout` | Requires multiple obscure commands and local git setup |
| SVN export (legacy) | Needs SVN installed, poor UX, increasingly unsupported |

When a repository has thousands of files across dozens of directories and you only need a single folder or a handful of files, all of these approaches waste your time, bandwidth, and disk space.

**GHPick solves this.** Paste a GitHub URL, get exactly those files. Nothing more.

## Key Features

- **Selective download** — Download a single file, a single folder, or multiple files and folders in one command
- **Folder structure preservation** — Downloaded content retains its original directory hierarchy
- **Automatic zip bundling** — Multi-target downloads are automatically archived into a zip; single files are saved directly
- **File preview** — List matched files with sizes before downloading anything
- **Glob-based filtering** — Include or exclude files by pattern (e.g., `--include "*.py"` or `--exclude tests`)
- **Interactive TUI browser** — Browse a repository's file tree visually, select files with checkboxes, and download your selection
- **GitHub token support** — Use a personal access token for higher API rate limits and private repository access
- **Rate limit awareness** — Displays your GitHub API quota after every operation; prompts for a token automatically when limits are exhausted
- **Progress bars** — Visual download progress powered by `tqdm` and `rich`

## Installation

**Requirements:** Python 3.11 or higher.

### From source (development)

```bash
git clone https://github.com/your-username/ghpick.git
cd ghpick
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e .
```

After installation, the `ghpick` command is available globally in your activated environment.

### Verify installation

```bash
ghpick --help
```

## Quick Start

```bash
# Download a folder (automatically saved as a zip archive)
ghpick https://github.com/user/repo/tree/main/backend

# Download a single file
ghpick https://github.com/user/repo/blob/main/model.py

# Preview what would be downloaded
ghpick https://github.com/user/repo/tree/main/src --list
```

## CLI Commands & Options

GHPick provides three commands: **`download`** (the default), **`browse`**, and **`rate-limit`**.

---

### `ghpick download` (default command)

Download files or folders from GitHub. This is the default command — you don't need to type `download` explicitly.

```bash
ghpick <url>... [OPTIONS]
ghpick download <url>... [OPTIONS]
```

#### Arguments

| Argument | Description |
|---|---|
| `<url>...` | One or more GitHub file or folder URLs. Folder URLs contain `/tree/` in the path; file URLs contain `/blob/`. |

#### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--output` | `-o` | `string` | `./downloads` | Output directory where files are saved. |
| `--zip` | | `flag` | auto | Force output as a zip archive, even for single files. |
| `--no-zip` | | `flag` | auto | Force flat file output, even for folders (no zip). |
| `--list` | `-l` | `flag` | `false` | Preview mode — list matched files with sizes instead of downloading. |
| `--include` | `-I` | `string` | *(none)* | Glob pattern to include files (can be specified multiple times). |
| `--exclude` | `-X` | `string` | *(none)* | Glob pattern to exclude files (can be specified multiple times). |
| `--ref` | | `string` | *(from URL)* | Override the branch, tag, or commit parsed from the URL. |

#### Examples

**Download a folder:**

```bash
ghpick https://github.com/user/repo/tree/main/backend
```

**Download a single file:**

```bash
ghpick https://github.com/user/repo/blob/main/model.py
```

**Download multiple targets at once:**

```bash
ghpick ^
  https://github.com/user/repo/blob/main/model.py ^
  https://github.com/user/repo/tree/main/backend ^
  https://github.com/user/repo/tree/main/docs
```

When all URLs come from the same repository, the zip is named `repo-selection.zip`. If URLs come from different repositories, it's named `ghpick-selection.zip` with paths prefixed by `owner/repo`.

**Preview files before downloading:**

```bash
ghpick https://github.com/user/repo/tree/main/src --list
```

Outputs a table showing each file's path, size, and type.

**Download only Python files from a folder:**

```bash
ghpick https://github.com/user/repo/tree/main/backend --include "*.py"
```

**Download everything except test files:**

```bash
ghpick https://github.com/user/repo/tree/main/backend --exclude tests
```

**Combine include and exclude:**

```bash
ghpick https://github.com/user/repo/tree/main/src --include "*.py" --exclude "*_test.py"
```

**Force zip output for a single file:**

```bash
ghpick https://github.com/user/repo/blob/main/model.py --zip
```

**Force flat (no-zip) output for a folder:**

```bash
ghpick https://github.com/user/repo/tree/main/backend --no-zip
```

**Specify a custom output directory:**

```bash
ghpick https://github.com/user/repo/tree/main/backend --output ./my-downloads
```

---

### `ghpick browse`

Launch an interactive terminal UI (TUI) to visually browse a repository's file tree, select files and folders, and download your selection.

```bash
ghpick browse <url> [OPTIONS]
```

#### Arguments

| Argument | Description |
|---|---|
| `<url>` | A GitHub repository URL (e.g., `https://github.com/user/repo`). |

#### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--output` | `-o` | `string` | `./downloads` | Output directory for downloaded files. |
| `--zip` | | `flag` | auto | Force output as a zip archive. |
| `--no-zip` | | `flag` | auto | Force flat file output (no zip). |
| `--ref` | | `string` | *(auto-detected)* | Branch, tag, or commit to browse. Defaults to the repo's default branch. |

#### TUI Keybindings

| Key | Action |
|---|---|
| `Space` | Toggle selection (check/uncheck) on the highlighted file or folder |
| `Enter` | Expand or collapse a folder (contents are lazy-loaded from the API) |
| `d` | Download all selected items |
| `r` | Refresh the file tree |
| `q` / `Ctrl+C` | Quit the browser |

#### Example

```bash
ghpick browse https://github.com/huggingface/transformers
```

---

### `ghpick rate-limit`

Display your current GitHub API rate limit status — total limit, requests used, requests remaining, and when the limit resets.

```bash
ghpick rate-limit
```

This is useful for checking your remaining quota before starting a large download, or for debugging 403 errors.

---

## GitHub API Authentication

GitHub's unauthenticated API allows **60 requests per hour**. With a personal access token, this increases to **5,000 requests per hour**.

GHPick searches for a token in the following environment variables (in order):

1. `GHPICK_TOKEN`
2. `GITHUB_TOKEN`
3. `GITHUB_ACCESS_TOKEN`
You can also place these in a `.env` file in the project root — GHPick loads it automatically via `python-dotenv`.

### Setting a token

**Windows (Command Prompt):**

```bash
set GITHUB_TOKEN=ghp_your_token_here
ghpick https://github.com/user/repo/tree/main/backend
```

**Windows (PowerShell):**

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
ghpick https://github.com/user/repo/tree/main/backend
```

**macOS / Linux:**

```bash
export GITHUB_TOKEN=ghp_your_token_here
ghpick https://github.com/user/repo/tree/main/backend
```

**Using a `.env` file:**

```env
GITHUB_TOKEN=ghp_your_token_here
```

### Automatic token prompt

If no token is configured and GitHub reports the unauthenticated rate limit is exhausted, GHPick will prompt you to enter a token interactively and retry the command once.

## Project Architecture

```
ghpick/
├── src/
│   └── ghpick/
│       ├── __init__.py            # Package version
│       ├── __main__.py            # python -m ghpick entry point
│       ├── exceptions.py          # Custom exception hierarchy
│       ├── cli/
│       │   ├── commands.py        # Click CLI commands (download, browse, rate-limit)
│       │   └── tui.py             # Textual TUI for interactive browsing
│       ├── github/
│       │   ├── parser.py          # GitHub URL parser
│       │   └── client.py          # GitHub API client (contents, trees, rate limits)
│       ├── downloader/
│       │   ├── file_downloader.py # File download with progress tracking
│       │   └── zip_creator.py     # Zip archive generation
│       ├── filters/
│       │   └── file_filter.py     # Include/exclude glob-based file filtering
│       └── utils/
│           └── filesystem.py      # Directory creation, filename sanitization, size formatting
├── tests/
│   ├── test_cli.py                # CLI command tests
│   ├── test_client.py             # GitHub API client tests
│   ├── test_filters.py            # File filter tests
│   ├── test_parser.py             # URL parser tests
│   └── test_zip_creator.py        # Zip creation tests
├── pyproject.toml                 # Build config, dependencies, entry points
├── requirements.txt               # Pinned dependencies
├── .env                           # Local environment variables (gitignored)
└── .gitignore
```

### How It Works

```
   GitHub URL(s)
        │
        ▼
   URL Parser ─────── Extracts owner, repo, branch, path, type (file/folder)
        │
        ▼
   GitHub API Client ─ Fetches file tree or single file via GitHub REST API
        │
        ▼
   File Filter ─────── Applies --include / --exclude glob patterns
        │
        ▼
   File Downloader ─── Downloads files with progress bars, preserving structure
        │
        ▼
   Zip Creator ─────── Optionally bundles output into a zip archive
        │
        ▼
   Output ──────────── Files saved to --output directory (default: ./downloads)
```

## Tech Stack

| Library | Purpose |
|---|---|
| [Click](https://click.palletsprojects.com/) | CLI framework — commands, arguments, options |
| [Requests](https://docs.python-requests.org/) | HTTP client for GitHub REST API |
| [Rich](https://rich.readthedocs.io/) | Beautiful terminal output — tables, panels, colors |
| [Textual](https://textual.textualize.io/) | Terminal UI framework for the interactive `browse` command |
| [tqdm](https://tqdm.github.io/) | Progress bars during file downloads |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Loads `.env` file for token configuration |

## Running Tests

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_parser.py
```

## Error Handling

GHPick provides clear, actionable error messages for common failure scenarios:

| Error | What Happens |
|---|---|
| Invalid GitHub URL | Explains the expected URL format (`/tree/` for folders, `/blob/` for files) |
| Repository not found (404) | Reports the owner/repo could not be found |
| API rate limit exceeded (403) | Shows remaining quota, prompts for a token |
| Network failure | Reports the connection error with retry guidance |
| Permission denied | Suggests using a token for private repositories |

## Roadmap

- **v2** — GitHub token support for private repositories and higher rate limits ✅
- **v3** — Smart dependency detection (auto-discover imported modules and suggest downloading them)
- **v4** — Browser extension ("Download with GHPick" context menu on GitHub)
- **v5** — Local web interface for visual file selection and download

## License

This project is open source. See the repository for license details.

## Author

Created and maintained by **H.M. Mehedi Hasan**.
