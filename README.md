
# Repo2Readme

Repo2Readme is an intelligent Python CLI tool designed to automate the creation of high-quality `README.md` files. It analyzes repository structures and leverages powerful Large 
Language Models (LLMs) like Groq and Google Gemini, integrated via LangChain, to generate comprehensive and professional documentation for any GitHub or local project. This tool 
streamlines the documentation process, ensuring your projects are well-explained and easily understood.

## Table of Contents

-   [Key Features](#key-features)
-   [Tech Stack](#tech-stack)
-   [Installation](#installation)
-   [Configuration](#configuration)
-   [Usage](#usage)
-   [Project Structure](#project-structure)
-   [How It Works](#how-it-works)
-   [License](#license)
-   [Credits](#credits)

## Key Features

✨ Automate README generation from any GitHub repository URL or local path.
🧠 AI-powered code summarization using Groq and Google Gemini models via LangChain.
⚡ Robust Command-Line Interface (CLI) built with Click.
🔍 Intelligent repository analysis and programming language detection.
🔑 Secure management of API keys for LLM services.

## Tech Stack

The Repo2Readme project is built using a modern Python ecosystem:

-   🐍 **Python** (3.10+) - The core programming language.
-   ⚡ **Click** - A powerful library for creating beautiful command-line interfaces.
-   ✨ **Rich** - For rich text and beautiful formatting in the terminal.
-   🔗 **LangChain** - Framework for developing applications powered by language models.
-   🛡️ **Pydantic** - Data validation and settings management using Python type hints.
-   🐙 **GitPython** - Python library to interact with Git repositories.
-   🧠 **Groq** - High-speed LLM inference provider (`langchain-groq`).
-   ♊ **Google Gemini** - Generative AI models from Google (`langchain-google-genai`).
-   🔑 **python-dotenv** - For loading environment variables from `.env` files.
-   🔄 **jsonpatch** - For applying JSON patch operations.
-   🤝 **langchain-community** - Community integrations for LangChain.

## Installation

To get started with Repo2Readme, ensure you have Python 3.10 or higher installed.

1.  **Clone the repository (optional, if installing from source):**
    ```bash
    git clone https://github.com/agsaru/repo2readme.git
    cd repo2readme
    ```

2.  **Install the package:**
    ```bash
    pip install repo2readme
    ```
    or, if installing from source:
    ```bash
    pip install .
    ```

## Configuration

Repo2Readme requires API keys for Groq and Google Gemini to interact with the Large Language Models. These keys are securely managed by the tool.

-   **API Keys Required:**
    -   `GROQ_API_KEY`: Your API key for Groq's LLM services.
    -   `GEMINI_API_KEY` (or `GOOGLE_API_KEY`): Your API key for Google Gemini (Generative AI) services.

-   **Key Management:**
    -   The first time you run a command that requires an API key, the tool will prompt you to enter it.
    -   Your keys are then securely saved in a JSON environment file located at `~/.repo2readme_env.json`.
    -   You can clear your stored API keys at any time using the `reset` command (see [Usage](#usage)).

## Usage

Repo2Readme provides a simple CLI to generate and manage your READMEs.

### Generate a README

You can generate a README from either a GitHub repository URL or a local path.

-   **From a GitHub Repository URL:**
    ```bash
    repo2readme run --url https://github.com/your-username/your-repo --output README.md
    ```
    Replace `https://github.com/your-username/your-repo` with the actual URL of the GitHub repository.

-   **From a Local Repository Path:**
    ```bash
    repo2readme run --local /path/to/your/local/repo --output README.md
    ```
    Replace `/path/to/your/local/repo` with the absolute or relative path to your local project directory.

### Reset API Keys

To clear all stored API keys (Groq and Google Gemini):

```bash
repo2readme reset
```

## Project Structure

```
Repo2Readme/
    ├── LICENSE
    ├── pyproject.toml
    ├── README.md
    ├── repo2readme/
        ├── config.py
        ├── cli/
            ├── main.py
        ├── loaders/
            ├── loader.py
            ├── repo_loader.py
        ├── readme/
            ├── agent_workflow.py
            ├── readme_generator.py
            ├── reviewer_agent.py
        ├── summerize/
            ├── summary.py
        ├── utils/
            ├── detect_language.py
            ├── filter.py
            ├── force_remove.py
            ├── tree.py
```

## How It Works

Repo2Readme operates through a well-defined architecture, orchestrating several modules to achieve its goal:

1.  **CLI Entry Point (`repo2readme/cli/main.py`):**
    -   This is the main command-line interface, built with `Click`.
    -   It orchestrates the entire workflow, handling commands like `run` (for README generation) and `reset` (for API key management).
    -   It uses `rich` for enhanced terminal output and progress bars.

2.  **Configuration Management (`repo2readme/config.py`):**
    -   Manages API keys for Groq and Google Gemini.
    -   It loads, saves, and retrieves keys from a JSON file (`~/.repo2readme_env.json`), interactively prompting the user if keys are missing.
    -   Provides functionality to reset (delete) stored keys.

3.  **Repository Loaders (`repo2readme/loaders/loader.py`, `repo2readme/loaders/repo_loader.py`):**
    -   `RepoLoader` acts as a facade, deciding whether to use `UrlRepoLoader` (for GitHub URLs) or `LocalRepoLoader` (for local paths).
    -   `UrlRepoLoader` clones remote Git repositories into temporary directories using `GitLoader` and cleans them up afterward.
    -   `LocalRepoLoader` walks local directories, filters files, and loads their content using `TextLoader`.
    -   Both loaders enrich documents with metadata like file path, name, and type. They leverage `github_file_filter` to ignore irrelevant files and directories.

4.  **Utility Functions (`repo2readme/utils/`):**
    -   `filter.py`: Defines `github_file_filter` to exclude common ignored files, directories, and extensions (e.g., `.git`, `node_modules`, binary files) from processing.      
    -   `detect_language.py`: `detect_lang` identifies the programming or markup language of a file based on its extension.
    -   `tree.py`: `extract_tree` generates a visual, indented representation of the repository's filtered directory structure and collects all relevant file paths.
    -   `force_remove.py`: A helper function `force_remove` used for safely deleting files and directories, even if they have restrictive permissions (e.g., read-only on
Windows).

5.  **Summarization (`repo2readme/summerize/summary.py`):**
    -   The `summarize_file` function creates a LangChain summarization chain.
    -   It uses a `ChatGroq` model (specifically `openai/gpt-oss-20b`) with a `JsonOutputParser` to generate structured, JSON-formatted summaries for each relevant source file.  
    -   Error handling is included to gracefully manage issues during summarization.

6.  **README Generation Workflow (`repo2readme/readme/`):**
    -   **Agent Workflow (`repo2readme/readme/agent_workflow.py`):**
        -   Defines a `LangGraph` workflow (`ReadmeState`) that orchestrates the README generation and review process.
        -   It includes nodes for `generate_readme` and `readme_reviewer`, with a conditional loop (`readme_condition`) to iterate on README improvements based on a review score 
and feedback.
    -   **README Generator (`repo2readme/readme/readme_generator.py`):**
        -   The `generate_readme` function takes file summaries, the repository tree structure, and optional reviewer feedback.
        -   It constructs a detailed `PromptTemplate` and uses a `ChatGroq` model (Llama 3.3) to produce the initial Markdown README.
    -   **Reviewer Agent (`repo2readme/readme/reviewer_agent.py`):**
        -   The `readme_reviewer` function acts as a "senior technical writer."
        -   It uses a `ChatGroq` model (Llama 3.3) and a `PydanticOutputParser` with a `ReviewSchema` to score the generated README (1-10) and provide actionable feedback for    
improvement.

This modular design ensures that each component handles a specific aspect of the README generation process, from repository analysis to AI-powered content creation and
refinement.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Sarowar Jahan Biswas

## Credits

Developed and maintained by Sarowar Jahan Biswas.