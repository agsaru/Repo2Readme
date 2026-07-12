# repo2readme

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/repo2readme?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/repo2readme)

Generate a professional `README.md` from any GitHub or local repository. `repo2readme` analyzes your project structure and file contents, then uses AI models to draft and iteratively refine a comprehensive, well-written README.

## 🌟 Table of Contents

- [About the Project](#about-the-project)
- [Quickstart](#quickstart)
- [Documentation](#documentation)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [How It Works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)

## About the Project

`repo2readme` is a command-line interface (CLI) tool designed to automate the creation of high-quality `README.md` files. It scans your repository, summarizes key files, and iteratively generates and refines a README using AI agents. Whether your project is hosted on GitHub or resides locally, `repo2readme` streamlines documentation so your projects stay well-explained and easy to understand.

## Quickstart

```bash
pip install repo2readme

# From a GitHub URL
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md

# From a local repo
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

On first run, you'll be prompted for a Groq and a Google Gemini API key. See [Configuration](docs/configuration.md) for details, or set them ahead of time:

```bash
export GROQ_API_KEY="your_groq_api_key"
export GOOGLE_API_KEY="your_google_api_key"
```

Want to preview what will be processed before spending any tokens? Use `--dry-run`:

```bash
repo2readme run --local ./path/to/your/repo --dry-run
```

## Documentation

Full details live in [`docs/`](docs/):

- [Installation](docs/installation.md)
- [Usage](docs/usage.md)
- [CLI Reference](docs/cli-reference.md) — every flag, explained
- [Configuration](docs/configuration.md) — API keys & environment variables
- [Examples](docs/examples.md) — common real-world commands
- [Troubleshooting](docs/troubleshooting.md)

## Key Features

- **Repository Analysis** — automatically loads files and content from GitHub URLs or local directories.
- **Intelligent Summarization** — uses a Groq LLM to summarize individual source files, capturing their purpose and functionality.
- **Hierarchical Tree Generation** — creates a visual representation of your repository's directory structure.
- **AI-Powered README Creation** — employs a Google Gemini model to draft comprehensive, structured `README.md` content.
- **Iterative Refinement** — a reviewer agent (Google Gemini) scores and improves the generated README until a high-quality standard is met.
- **API Key Management** — securely stores and manages API keys for Groq and Google Gemini in your local environment.
- **File Filtering** — automatically ignores common development artifacts (`.git`, `node_modules`, `__pycache__`, lock files, images, archives, etc.), with `--include`/`--exclude`/`--max-file-size-kb` for fine control.

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

## Folder Structure

```
Repo2Readme/
    ├── README.md
    ├── CODE_OF_CONDUCT.md
    ├── CONTRIBUTING.md
    ├── LICENSE
    ├── pyproject.toml
    ├── requirements.txt
    ├── docs/
    │   ├── installation.md
    │   ├── usage.md
    │   ├── cli-reference.md
    │   ├── configuration.md
    │   ├── examples.md
    │   └── troubleshooting.md
    ├── repo2readme/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── cli/
    │   │   ├── __init__.py
    │   │   └── main.py
    │   ├── llm/
    │   │   ├── __init__.py
    │   │   └── factory.py
    │   ├── loaders/
    │   │   ├── __init__.py
    │   │   ├── loader.py
    │   │   └── repo_loader.py
    │   ├── readme/
    │   │   ├── __init__.py
    │   │   ├── agent_workflow.py
    │   │   ├── readme_generator.py
    │   │   └── reviewer_agent.py
    │   ├── summarize/
    │   │   ├── __init__.py
    │   │   └── summary.py
    │   └── utils/
    │       ├── __init__.py
    │       ├── detect_language.py
    │       ├── filter.py
    │       ├── force_remove.py
    │       └── tree.py
    ├── tests/
    └── .github/
        ├── dependabot.yml
        └── workflows/
```

## How It Works

1. **Repository Loading** — a `RepoLoader` picks a `UrlRepoLoader` (clones the GitHub repo into a temp directory) or `LocalRepoLoader` (reads your filesystem), and applies `github_file_filter` to skip irrelevant files (`.git`, `node_modules`, `package-lock.json`, `.env`, binaries, etc.).
2. **Structure & File Analysis** — `generate_tree` builds a visual directory tree; each file's language is detected via `detect_lang`; `summarize_file` uses a Groq LLM (`openai/gpt-oss-120b`) to produce a concise, JSON-formatted summary of each file's purpose.
3. **Iterative README Generation** — a LangGraph state machine alternates between:
   - **Generation** (`generate_readme_node`, Gemini 2.5 Flash) — drafts a README from file summaries, the repo tree, prior drafts, and reviewer feedback.
   - **Review** (`readme_reviewer_node`, Gemini 2.5 Flash) — scores the draft (1–10) with feedback.
   - The loop stops once the README scores 8.5+ or a max iteration count is hit.
4. **Output** — the best-scoring README is printed or saved to your chosen output file (default `README.md`).

`repo2readme/config.py` handles secure API key storage/loading, and `force_remove` safely cleans up temporary clone directories.

See the [CLI Reference](docs/cli-reference.md) for the full list of flags, including file filtering options.

## Contributing

Contributions are welcome! Whether you're fixing bugs, improving documentation, or adding new features, your help is appreciated. Please read the [Contributing Guide](CONTRIBUTING.md) for setup, coding standards, and the pull request process. By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2025 Sarowar Jahan Biswas