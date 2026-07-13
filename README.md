# repo2readme

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/repo2readme?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/repo2readme)

Generate a professional `README.md` from any GitHub or local repository. `repo2readme` analyzes your project structure and file contents, then uses AI models to draft and iteratively refine a comprehensive, well-written README.

## 🌟 Table of Contents

- [About the Project](#about-the-project)
- [Key Features](#key-features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Tech Stack](#tech-stack)
- [How It Works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)

## About the Project

`repo2readme` is a command-line interface (CLI) tool designed to automate the creation of high-quality `README.md` files. It scans your repository, summarizes key files, and iteratively generates and refines a README using AI agents. Whether your project is hosted on GitHub or resides locally, `repo2readme` streamlines documentation so your projects stay well-explained and easy to understand.

## Key Features

- **Repository Analysis** — automatically loads files and content from GitHub URLs or local directories.
- **Intelligent Summarization** — uses a Groq LLM to summarize individual source files, capturing their purpose and functionality.
- **Hierarchical Tree Generation** — creates a visual representation of your repository's directory structure.
- **AI-Powered README Creation** — employs a Google Gemini model to draft comprehensive, structured `README.md` content.
- **Iterative Refinement** — a reviewer agent (Google Gemini) scores and improves the generated README until a high-quality standard is met.
- **File Filtering** — automatically ignores common development artifacts (`.git`, `node_modules`, `__pycache__`, lock files, images, archives, etc.), with `--include`/`--exclude`/`--max-file-size-kb` for fine control.

## Installation

Requires Python 3.10+.

```bash
pip install repo2readme
```

Or install from source:

```bash
git clone https://github.com/agsaru/repo2readme.git
cd repo2readme
pip install -e .
```

Verify it installed:

```bash
repo2readme --help
```

## Usage

`repo2readme` provides two commands: `run` to generate a README, and `reset` to clear stored API keys.

### Generate a README

**From a GitHub repository URL:**
```bash
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md
```

**From a local repository path:**
```bash
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--url <URL>` | `-u` | GitHub repository URL to process. |
| `--local <PATH>` | `-l` | Path to a local repository. |
| `--output <FILE_PATH>` | `-o` | Output file path (defaults to `README.md`). |
| `--force` | `-f` | Overwrite output and skip the confirmation prompt. |
| `--dry-run` | | Preview file selection & token estimate — no API calls, no keys required. |
| `--include <PATTERN>` | | Glob pattern to force-include a file, even if normally filtered. |
| `--exclude <PATTERN>` | | Glob pattern to exclude a file. |
| `--max-file-size-kb <N>` | | Skip files larger than N KB. |

You must provide exactly one of `--url` or `--local`.

### Token estimation & confirmation

Before making any API calls, `repo2readme` estimates file count, token usage, and request size, then asks for confirmation:

```
Repository Analysis

Files to summarize : 45
Estimated tokens   : ~120,000
Request size       : ~420.5 KB

Proceed? [y/N]
```

Pass `--force` to skip this prompt and overwrite the output automatically.

### Dry run mode

Preview what will be processed — no API calls, no API keys needed:

```bash
repo2readme run --local ./path/to/your/repo --dry-run
```

```
Repository Tree

project/
├── src/
├── tests/
└── README.md

Files to be processed

✓ src/main.py
✓ src/api.py
✓ tests/test_api.py
...

Repository Analysis

Files selected     : 45
Estimated tokens   : ~120,000
Request size       : ~420.5 KB

Dry run complete.
No API requests were made.
```

### Filtering files

Default filters skip generated files, build artifacts, lock files, images, archives, and similar noise. Adjust with `--include`/`--exclude`/`--max-file-size-kb`:

```bash
repo2readme run --local ./my-project --include "package.json"
repo2readme run --local ./my-project --exclude "tests/*"
repo2readme run --local ./my-project --include "*.json" --max-file-size-kb 200
```

### Reset stored API keys

```bash
repo2readme reset
```
Deletes the local key config file; you'll be re-prompted on the next `run`.

## Configuration

`repo2readme` needs two API keys:

| Variable | Used for |
|---|---|
| `GROQ_API_KEY` | File summarization (Groq `openai/gpt-oss-120b`) |
| `GOOGLE_API_KEY` | README generation & review (Gemini `2.5-flash`) |

On first run, the CLI prompts for these interactively and saves them to `~/.repo2readme_env.json` for future runs. Alternatively, set them as environment variables:

```bash
export GROQ_API_KEY="your_groq_api_key"
export GOOGLE_API_KEY="your_google_api_key"
```

## Tech Stack

- 🐍 Python (>=3.10)
- 🛠️ Setuptools
- 🖱️ Click — CLI interface
- ✨ Rich — terminal output & progress displays
- ⚙️ GitPython — Git repository interaction
- 🔑 python-dotenv — environment variable management
- 🦜 LangChain (+ Community, Groq, Google GenAI integrations)
- 💨 Groq — fast inference (`openai/gpt-oss-120b` for summarization)
- 🚀 Google GenAI — Gemini models (`gemini-2.5-flash` for generation & review)
- Pydantic — data validation for the reviewer agent schema

## How It Works

1. **Repository Loading** — a `RepoLoader` picks a `UrlRepoLoader` (clones the GitHub repo into a temp directory) or `LocalRepoLoader` (reads your filesystem), and applies `github_file_filter` to skip irrelevant files (`.git`, `node_modules`, `package-lock.json`, `.env`, binaries, etc.).
2. **Structure & File Analysis** — `generate_tree` builds a visual directory tree; each file's language is detected via `detect_lang`; `summarize_file` uses a Groq LLM to produce a concise, JSON-formatted summary of each file's purpose.
3. **Iterative README Generation** — a LangGraph state machine alternates between:
   - **Generation** (`generate_readme_node`, Gemini 2.5 Flash) — drafts a README from file summaries, the repo tree, prior drafts, and reviewer feedback.
   - **Review** (`readme_reviewer_node`, Gemini 2.5 Flash) — scores the draft (1–10) with feedback.
   - The loop stops once the README scores 8.5+ or a max iteration count is hit.
4. **Output** — the best-scoring README is printed or saved to your chosen output file (default `README.md`).

`repo2readme/config.py` handles secure API key storage/loading, and `force_remove` safely cleans up temporary clone directories.

## Contributing

Contributions are welcome! Whether you're fixing bugs, improving documentation, or adding new features, your help is appreciated. Please read the [Contributing Guide](CONTRIBUTING.md) for setup, coding standards, and the pull request process. By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2025 Sarowar Jahan Biswas