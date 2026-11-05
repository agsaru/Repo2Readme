# Installation

## Requirements

- Python 3.10 or higher
- pip

## Install from PyPI

The default installation includes the Groq integration:

```bash
pip install repo2readme
```

Other model integrations are optional. Install the one you plan to use:

```bash
pip install "repo2readme[google]"    # Google Gemini
pip install "repo2readme[openai]"    # OpenAI, OpenRouter, and Together
pip install "repo2readme[anthropic]" # Anthropic
pip install "repo2readme[ollama]"    # Local Ollama
```

You can install more than one integration at once:

```bash
pip install "repo2readme[google,ollama]"
```

## Install from source

```bash
git clone https://github.com/agsaru/repo2readme.git
cd repo2readme
pip install -e .
```

For development and tests:

```bash
pip install -e ".[dev]"
pytest
```

## Verify the installation

```bash
repo2readme --help
```

## Next steps

- [Usage guide](./usage.md) — generate your first README
- [Configuration](./configuration.md) — set up your API keys
