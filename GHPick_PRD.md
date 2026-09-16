# Product Requirements Document (PRD)

# GHPick --- Selective GitHub File & Folder Downloader CLI

## 1. Product Overview

GHPick is a lightweight developer CLI tool that allows users to download
specific files or folders from public GitHub repositories without
cloning the entire repository.

The goal is to solve the common developer problem:

> "I only need one folder/file from a large GitHub repository, but
> GitHub only provides full repository download."

------------------------------------------------------------------------

# 2. Problem Statement

Developers frequently explore GitHub repositories for:

-   ML models
-   Backend implementations
-   Algorithms
-   Documentation
-   Code examples

Large repositories contain many unnecessary files. Users often need only
a specific folder or file.

Current approaches:

  Solution              Problem
  --------------------- -----------------------------
  Git clone             Downloads everything
  GitHub ZIP            Downloads entire repository
  Git sparse checkout   More complex commands
  SVN export            Limited user experience

------------------------------------------------------------------------

# 3. Goals

## Primary Goals

-   Download specific GitHub folders
-   Download individual files
-   Preserve folder structure
-   Generate ZIP archives
-   Support branches
-   Provide a simple CLI experience

## Non Goals

Initial version will not support:

-   Repository modification
-   Git history management
-   Uploading files
-   Collaboration
-   Cloud deployment

------------------------------------------------------------------------

# 4. Target Users

## Developers

Users who:

-   Explore open-source repositories
-   Learn from GitHub projects
-   Extract specific modules
-   Download ML source code

------------------------------------------------------------------------

# 5. User Stories

## Download Folder

As a developer, I want to provide a GitHub folder URL so that I can
download only that folder.

Example:

``` bash
ghpick https://github.com/user/repo/tree/main/backend
```

Output:

    backend.zip

------------------------------------------------------------------------

## Download File

Example:

``` bash
ghpick https://github.com/user/repo/blob/main/model.py
```

Output:

    model.py

------------------------------------------------------------------------

## Preview Files

Command:

``` bash
ghpick URL --list
```

Example:

    model.py       12KB
    config.json     2KB
    tokenizer.py    8KB

------------------------------------------------------------------------

# 6. Functional Requirements

## GitHub URL Processing

Support:

Folder URLs:

    github.com/user/repo/tree/main/path

File URLs:

    github.com/user/repo/blob/main/file.py

Extract:

-   Owner
-   Repository
-   Branch
-   Path

------------------------------------------------------------------------

## Repository Information Retrieval

Use GitHub Contents API:

    GET /repos/{owner}/{repo}/contents/{path}

------------------------------------------------------------------------

## Recursive Folder Download

The system should:

1.  Detect directories
2.  Enter directories recursively
3.  Download files
4.  Maintain folder structure

Example:

    backend/

    ├── api.py
    ├── database.py
    └── auth/
        └── jwt.py

------------------------------------------------------------------------

## ZIP Generation

Support:

``` bash
--zip
```

Output:

    project-folder.zip

------------------------------------------------------------------------

# 7. CLI Design

Basic:

``` bash
ghpick <github-url>
```

Options:

## Output

``` bash
--output ./downloads
```

## ZIP

``` bash
--zip
```

## Preview

``` bash
--list
```

## Filter

``` bash
--include "*.py"
```

## Exclude

``` bash
--exclude tests
```

------------------------------------------------------------------------

# 8. System Architecture

    User

     |

    CLI Application

     |

    URL Parser

     |

    GitHub API Client

     |

    Repository Tree

     |

    File Downloader

     |

    File Manager

     |

    ZIP Generator

     |

    Output

------------------------------------------------------------------------

# 9. Technical Stack

## Language

Python 3.11+

## Libraries

    requests
    click
    tqdm
    rich
    python-dotenv

------------------------------------------------------------------------

# 10. Project Structure

    ghpick/

    ├── src/
    │
    ├── cli/
    │   └── commands.py
    │
    ├── github/
    │   ├── parser.py
    │   └── client.py
    │
    ├── downloader/
    │   ├── file_downloader.py
    │   └── zip_creator.py
    │
    ├── filters/
    │   └── file_filter.py
    │
    ├── utils/
    │   └── filesystem.py
    │
    ├── tests/
    │
    ├── requirements.txt
    ├── README.md
    └── pyproject.toml

------------------------------------------------------------------------

# 11. Error Handling

Handle:

-   Invalid GitHub URL
-   Repository not found
-   API rate limits
-   Network interruptions
-   Missing permissions

------------------------------------------------------------------------

# 12. Advanced Features Roadmap

## Version 2

### GitHub Token Support

Benefits:

-   Higher API limits
-   Private repository support

------------------------------------------------------------------------

## Version 3

### Smart Dependency Detection

Example:

If downloading:

    model.py

Detect imports:

``` python
import utils
import config
```

Suggest downloading dependencies.

------------------------------------------------------------------------

## Version 4

### Browser Extension

Right click GitHub folder:

    Download with GHPick

------------------------------------------------------------------------

## Version 5

### Local Web Interface

Features:

-   Paste GitHub URL
-   Browse repository tree
-   Select files
-   Download ZIP

------------------------------------------------------------------------

# 13. Security

Avoid:

-   Executing downloaded code
-   Automatically running scripts
-   Unsafe token storage

Use:

-   Environment variables
-   OS keychain

------------------------------------------------------------------------

# 14. Testing

## Unit Tests

Test:

-   URL parser
-   API client
-   Filters
-   ZIP creation

## Integration Tests

Flow:

    GitHub URL
       |
    Download
       |
    Verify files

------------------------------------------------------------------------

# 15. MVP Acceptance Criteria

The first release should:

-   Download GitHub folders
-   Download individual files
-   Preserve structure
-   Create ZIP files
-   Provide CLI commands
-   Handle errors properly

------------------------------------------------------------------------

# 16. Development Timeline

## Phase 1

Duration: 2 days

Build:

-   URL parser
-   GitHub API client
-   Recursive downloader

## Phase 2

Duration: 1 day

Build:

-   CLI
-   Arguments
-   Progress display

## Phase 3

Duration: 2 days

Add:

-   Filtering
-   Preview
-   Configuration
-   Better errors

------------------------------------------------------------------------

# 17. Product Vision

GHPick becomes:

> "The easiest way for developers to grab exactly what they need from
> any GitHub repository."

Example:

``` bash
ghpick https://github.com/huggingface/transformers/tree/main/src/transformers/models/llama
```

Output:

    Scanning repository...

    23 files found

    Downloading...

    100%

    Saved:
    llama-models.zip
