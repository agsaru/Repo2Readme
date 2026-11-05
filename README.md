# repo2readme

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/repo2readme?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/repo2readme)

Generate a professional `README.md` from any GitHub or local repository. `repo2readme` analyzes your project structure and file contents, then uses an AI model to draft and refine a comprehensive README.

## Table of Contents

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

`repo2readme` is a command-line tool that automates the creation of project documentation. It scans a repository, summarizes relevant files, and generates a README using the configured language model. It works with local directories and Git repositories.

## Key Features

- **Repository Analysis** — loads files from local directories or Git URLs.
- **File Summarization** — summarizes source files using the configured language model.
- **Repository Structure** — includes the analyzed file tree in the generated README.
- **README Generation and Review** — generates a README and can refine it using reviewer feedback.
- **File Filtering** — skips common development artifacts and supports include, exclude, and file-size options.
- **Summary Cache** — reuses summaries when files have not changed.

## Installation

Requires Python 3.10 or higher.

Install the default setup (Groq provider):

```bash
pip install repo2readme
```

Install optional provider integrations only when you need them:

```bash
pip install "repo2readme[google]"    # Google Gemini
pip install "repo2readme[openai]"    # OpenAI, OpenRouter, and Together
pip install "repo2readme[anthropic]" # Anthropic
pip install "repo2readme[ollama]"    # Local Ollama
```

You can combine extras, for example:

```bash
pip install "repo2readme[google,ollama]"
```

Or install from source:

```bash
git clone https://github.com/agsaru/repo2readme.git
cd repo2readme
pip install -e .
```

Verify the installation:

```bash
repo2readme --help
```

## Usage

Generate a README from a Git repository:

```bash
repo2readme run --url https://github.com/owner/project
```

Or from a local repository:

```bash
repo2readme run --local ./path/to/project
```

Preview the files that will be analyzed without making API calls:

```bash
repo2readme run --local . --dry-run
```

Use a different provider:

```bash
repo2readme run --local . --provider google
repo2readme run --local . --provider ollama --model llama3
```

Use `repo2readme run --help` to see all available options.

## Configuration

The default provider is Groq. Set its API key before running:

```bash
export GROQ_API_KEY="your_groq_api_key"
```

You can also configure API keys through the CLI's interactive prompt. Other providers use their respective environment variables:

| Provider | Environment variable |
|---|---|
| Groq | `GROQ_API_KEY` |
| Google Gemini | `GOOGLE_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Together AI | `TOGETHER_API_KEY` |
| Ollama | No API key required |

For OpenAI-compatible providers, use `--base-url` when a custom endpoint is needed. OpenRouter and Together AI have built-in base URLs.

## Tech Stack

- Python 3.10+
- Click and Rich for the CLI
- Git CLI for cloning repositories and PathSpec for `.gitignore` matching
- LangChain for model calls and a simple Python review loop
- Groq as the default model integration
- Optional integrations for Google, OpenAI-compatible providers, Anthropic, and Ollama

## How It Works

1. **Load the repository** — read a local directory or clone a Git repository.
2. **Select files** — apply default ignore rules and the user's include, exclude, and size settings.
3. **Analyze files** — detect file types, build the repository tree and summarize the selected files.
4. **Generate the README** — use the summaries and repository structure to create a README.
5. **Review the result** — when enabled by the workflow, use reviewer feedback to improve the draft.
6. **Save the output** — print the README or write it to the requested path.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup and contribution guidelines. Please also follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
