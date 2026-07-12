# repo2readme

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/repo2readme?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/repo2readme)

Generate a professional `README.md` from any GitHub or local repository. `repo2readme` analyzes your project structure and file contents, then uses AI models to draft and iteratively refine a comprehensive README.

## Quickstart

```bash
pip install repo2readme

# From a GitHub URL
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md

# From a local repo
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

On first run you'll be prompted for a Groq and a Google Gemini API key — see [Configuration](docs/configuration.md) for details.

## Documentation

- [Installation](docs/installation.md)
- [Usage](docs/usage.md)
- [CLI Reference](docs/cli-reference.md)
- [Configuration](docs/configuration.md)
- [Examples](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)

## Key Features

- **Repository Analysis** — loads files from a GitHub URL or a local directory.
- **Intelligent Summarization** — a Groq LLM summarizes each source file's purpose and functionality.
- **Hierarchical Tree Generation** — a visual directory tree of your project.
- **AI-Powered README Creation** — a Google Gemini model drafts the README.
- **Iterative Refinement** — a reviewer agent scores and improves drafts until quality is high enough.
- **File Filtering** — common non-essential files (`.git`, `node_modules`, `__pycache__`, etc.) are skipped automatically, and configurable via `--include`/`--exclude`/`--max-file-size-kb`.

## Tech Stack

Python (>=3.10) · Click · Rich · GitPython · python-dotenv · LangChain (+ Groq and Google GenAI integrations) · Pydantic

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) for setup, coding standards, and the PR process. By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT License. See [LICENSE](LICENSE).
