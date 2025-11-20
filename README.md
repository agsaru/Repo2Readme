
# Repo2Readme

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


Repo2Readme is a powerful Python-based command-line interface (CLI) tool designed to effortlessly generate clean,
polished, and professional `README.md` files. It analyzes your repository's structure and code, then leverages large
language models to create a comprehensive and user-friendly documentation for your project.

Whether you're starting a new project or need to quickly document an existing one, Repo2Readme streamlines the process,
ensuring your project has a high-quality README without manual effort.

## 📖 Table of Contents

- [✨ Features](#-features)
- [🛠️ Tech Stack](#%F0%9F%9B%A0%EF%B8%8F-tech-stack)
- [📂 Folder Structure](#-folder-structure)
- [🚀 Installation](#-installation)
- [⚙️ Configuration](#%E2%9A%99%EF%B8%8F-configuration)
- [💡 Usage](#-usage)
- [🧠 How the Code Works](#-how-the-code-works)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Credits](#-credits)

## ✨ Features

Repo2Readme offers a suite of features to simplify your documentation workflow:

-   **Automatic README Generation**: Effortlessly create `README.md` files from any GitHub repository URL or local
project path.
-   **Intelligent Summarization**: Leverages advanced AI models (Groq, Google GenAI) via LangChain to understand and
summarize code files.
-   **CLI Interface**: A user-friendly command-line interface built with Click for easy interaction.
-   **Repository Analysis**: Automatically detects programming languages and filters out irrelevant files for focused
documentation.
-   **API Key Management**: Securely manage and reset your API keys for AI services.

## 🛠️ Tech Stack

Repo2Readme is built using a modern Python ecosystem, leveraging powerful libraries for CLI development, AI integration,
and repository management.

-   **Python** 🐍: The core programming language.
-   **Click** ⚡: For building beautiful and robust command-line interfaces.
-   **Rich** ✨: For rich text and beautiful formatting in the terminal.
-   **LangChain** 🔗: A framework for developing applications powered by language models.
-   **Pydantic** ✅: For data validation and settings management.
-   **GitPython** 🐙: Python library to interact with Git repositories.
-   **Groq** 🚀: Utilized via `langchain-groq` for high-performance language model inference.
-   **Google GenAI** 🧠: Utilized via `langchain-google-genai` for integrating Google's generative AI models.
-   **python-dotenv** 🔑: For loading environment variables from `.env` files.
-   **jsonpatch** 🧩: For applying JSON patch operations.

## 📂 Folder Structure

The repository is organized into a modular structure to separate concerns and enhance maintainability:

```
Repo2Readme/
    ├── .gitignore
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
            ├── readme_generator.py
        ├── summerize/
            ├── schema.py
            ├── summary.py
        ├── utils/
            ├── detect_language.py
            ├── filter.py
            ├── force_remove.py
            ├── tree.py
```

## 🚀 Installation

To get started with Repo2Readme, follow these simple steps:

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/Repo2Readme.git
    cd Repo2Readme
    ```

2.  **Create and activate a virtual environment (recommended):**

    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install poetry
    poetry install
    ```
    Alternatively, if using `pip` directly:
    ```bash
    pip install -e .
    ```

## ⚙️ Configuration

Repo2Readme requires API keys for Groq and Google Gemini to interact with the language models. These keys are managed
through a configuration file.

Upon first use, the tool will prompt you to enter your API keys. They will be securely stored.

To explicitly set or update your API keys, you can create a `.env` file in the root of the project with the following
variables:

```dotenv
GROQ_API_KEY="your_groq_api_key_here"
GEMINI_API_KEY="your_gemini_api_key_here"
```

Alternatively, the tool will guide you through the process, loading and saving environment variables as needed.

## 💡 Usage

Repo2Readme is a command-line tool. Here's how you can use it:

### Generate a README for a GitHub Repository

To generate a `README.md` file from a GitHub repository URL:

```bash
repo2readme run --url https://github.com/owner/repository --output README.md
```

-   `--url`: The GitHub repository URL.
-   `--output`: The path where the generated `README.md` will be saved.

### Generate a README for a Local Repository

To generate a `README.md` file from a local repository path:

```bash
repo2readme run --local /path/to/your/local/repo --output README.md
```

-   `--local`: The path to your local repository folder.
-   `--output`: The path where the generated `README.md` will be saved.

### Reset Stored API Keys

If you need to clear your stored API keys, use the `reset` command:

```bash
repo2readme reset
```

This command will remove the environment file where API keys are stored, prompting you to re-enter them on the next run.

## 🧠 How the Code Works

Repo2Readme orchestrates several modules to achieve its goal of generating a comprehensive README:

1.  **CLI Entry Point (`repo2readme/cli/main.py`)**: This is the main command-line interface for the tool, built with
`Click`. It handles parsing arguments like repository URLs, local paths, and output file paths, and orchestrates the
overall workflow. It also provides a `reset` command to clear stored API keys.

2.  **Configuration (`repo2readme/config.py`)**: This module is responsible for loading and saving environment
variables, particularly for API keys (Groq and Gemini). It provides functions to `load_env`, `save_env`, `get_api_keys`
(which prompts the user if keys are missing), and `reset_api_keys` (which removes the environment file).

3.  **Repository Loading (`repo2readme/loaders/loader.py`, `repo2readme/loaders/repo_loader.py`)**:
    -   `loader.py` contains classes like `LocalRepoLoader` for handling local repository folders and `UrlRepoLoader`
for cloning repositories from a given URL (defaulting to the 'main' branch).
    -   `repo_loader.py` provides the `RepoLoader` class, which acts as a unified interface to load repositories from
either a URL or a local path, abstracting away the underlying loading mechanism.

4.  **Utility Functions (`repo2readme/utils/`)**:
    -   **Language Detection (`detect_language.py`)**: Contains a dictionary mapping file extensions to programming
languages and a `detect_lang` function to identify the language of a file based on its extension.
    -   **File Filtering (`filter.py`)**: Includes `github_file_filter`, a function to filter out unwanted files and
directories (e.g., `.git`, `node_modules`) commonly found in GitHub repositories, ensuring only relevant files are
processed.
    -   **Force Remove (`force_remove.py`)**: A utility to force removal of read-only files, often used in cleanup
operations.
    -   **Tree Generation (`tree.py`)**: Provides functions like `generate_tree` to create a visual tree structure of a
directory and `extract_tree` to extract both the tree structure and a list of all relevant file paths within a
repository.

5.  **Summarization (`repo2readme/summerize/schema.py`, `repo2readme/summerize/summary.py`)**:
    -   `schema.py` defines the Pydantic schema for the `CodeSummary` object, ensuring generated summaries conform to a
required structure (file path, language, short description, functions, imports, exports).
    -   `summary.py` contains the core logic for AI-powered summarization. It includes `create_summarizer` to set up a
summarizer function and `summarize_file` which takes file content, path, and language, then uses LangChain with Groq or
Google GenAI to generate a structured JSON summary matching the defined schema.

6.  **README Generation (`repo2readme/readme/readme_generator.py`)**: This module is responsible for synthesizing all
the gathered information into the final `README.md`. It takes the list of file summaries, the repository's tree
structure, and file paths as input. It uses LangChain prompts and output parsers, powered by Groq or Google GenAI, to
generate a comprehensive and well-formatted `README.md` file.

7.  **Project Metadata (`pyproject.toml`)**: This file, along with `setup.cfg` (if it were present), specifies project
metadata, dependencies (like Click, Rich, LangChain, GitPython, Groq, Google GenAI, python-dotenv, jsonpatch), build
backend, and entry points for the `repo2readme` command.

In essence, Repo2Readme loads your code, intelligently filters and summarizes it using AI, and then uses another AI
model to generate a polished `README.md` based on the extracted information and the repository's structure.

## 🤝 Contributing

We welcome contributions to Repo2Readme! If you have suggestions for improvements, new features, or bug fixes, please
feel free to:

1.  **Fork the repository.**
2.  **Create a new branch** (`git checkout -b feature/your-feature-name`).
3.  **Make your changes.**
4.  **Commit your changes** (`git commit -m 'feat: Add new feature'`).
5.  **Push to the branch** (`git push origin feature/your-feature-name`).
6.  **Open a Pull Request.**

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## 🙏 Credits

Repo2Readme is built upon the incredible work of the open-source community. Special thanks to the developers and
maintainers of:

-   [Python](https://www.python.org/)
-   [Click](https://palletsprojects.com/p/click/)
-   [Rich](https://github.com/Textualize/rich)
-   [LangChain](https://www.langchain.com/)
-   [Pydantic](https://pydantic.dev/)
-   [GitPython](https://gitpython.readthedocs.io/en/stable/)
-   [Groq](https://groq.com/)
-   [Google GenAI](https://ai.google.dev/models/gemini)
-   (https://github.com/theskumar/python-dotenv)
-   (https://jsonpatch.readthedocs.io/en/latest/)

Your contributions make projects like this possible!
developers of `Click`, `Rich`, `LangChain`, `Pydantic`,       
`GitPython`, and other libraries that made this project       
possible.
