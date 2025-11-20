# 🚀 Repo2Readme

[![Python
Version](https://img.shields.io/badge/python-3.9+-blue.svg)](h
ttps://www.python.org/downloads/)
[![License:
MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LIC
ENSE)
[![GitHub
Stars](https://img.shields.io/github/stars/your-username/Repo2
Readme?style=social)](https://github.com/your-username/Repo2Re
adme/stargazers)
[![GitHub
Forks](https://img.shields.io/github/forks/your-username/Repo2
Readme?style=social)](https://github.com/your-username/Repo2Re
adme/network/members)

Repo2Readme is a powerful Python-based command-line interface (CLI) tool designed to effortlessly generate clean, polished, and professional `README.md` files. Whether you're working with a GitHub repository or a local project, Repo2Readme streamlines the documentation process, helping you present your work clearly and professionally.

---

## 📋 Table of Contents

-   [🚀 Project Title](#-project-title)
-   [✨ Short Description](#-short-description)
-   [🛠️ Tech Stack](#%EF%B8%8F-tech-stack)
-   [🌟 Key Features](#-key-features)
-   [📂 Folder Structure](#-folder-structure)
-   [⚙️ Installation](#%EF%B8%8F-installation)
-   [🚀 Usage](#-usage)
-   [🔑 Configuration / Environment Variables](#-configuration--environment-variables)
-   [💡 How the Code Works](#-how-the-code-works)
-   [🤝 Contributing](#-contributing)
-   [📄 License](#-license)
-   [🙏 Credits / Acknowledgements](#-credits--acknowledgements)

---

## ✨ Short Description

Repo2Readme is your go-to CLI tool for automating `README.md` generation. It intelligently analyzes your repository, summarizes its contents, and crafts a comprehensive, high-quality README, saving you valuable time and ensuring consistent project documentation. It supports both remote GitHub URLs and local file system paths.

---

## 🛠️ Tech Stack

Repo2Readme leverages a robust set of modern Python libraries and frameworks:

*   **Python** 🐍: The core programming language.
*   **Click** ⚡: For building the intuitive command-line interface.
*   **Rich** ✨: Enhances CLI output with beautiful formatting, colors, and progress bars.
*   **LangChain** 🔗: Powers the intelligent summarization and README generation through large language models.
*   **Pydantic** ✅: Ensures data validation and settings management.
*   **GitPython** 🐙: Used for interacting with Git repositories, particularly for cloning remote URLs.
*   **Groq** 🧠: Integrates with Groq's language models for high-performance content generation.
*   **Google GenAI** 🤖: Utilizes Google's Generative AI models for diverse content generation capabilities.
*   **python-dotenv** ⚙️: Manages environment variables for API keys and configuration.

---

## 🌟 Key Features

*   **Effortless README Generation**: Automatically creates `README.md` files from repository content.
*   **GitHub Repository Support**: Generate READMEs directly from GitHub URLs.
*   **Local Project Compatibility**: Works seamlessly with local directories.
*   **Clean & Professional Output**: Produces well-structured and polished documentation.
*   **API Key Management**: Easy configuration and resetting of API keys for LLM services.
*   **Intelligent Summarization**: Leverages LLMs to understand and summarize code and project structure.

---

## 📂 Folder Structure

```
Repo2Readme/
├── .gitignore
├── LICENSE
├── pyproject.toml
├── README.md
├── repo2readme/
│   ├── config.py
│   ├── cli/
│   │   └── main.py
│   ├── loaders/
│   │   ├── loader.py
│   │   └── repo_loader.py
│   ├── readme/
│   │   └── readme_generator.py
│   ├── summerize/
│   │   ├── schema.py
│   │   └── summary.py
│   ├── utils/
│   │   ├── detect_language.py
│   │   ├── filter.py
│   │   ├── force_remove.py
│   │   └── tree.py
└── repo2readme.egg-info/
    └── PKG-INFO
```

---

## ⚙️ Installation

To get started with Repo2Readme, follow these simple steps:

1.  **Clone the repository (if installing from source):**
    ```bash
    git clone https://github.com/your-username/Repo2Readme.git
    cd Repo2Readme
    ```

2.  **Install the package:**
    It's recommended to install Repo2Readme in a virtual environment.

    ```bash
    # Create a virtual environment
    python -m venv venv
    # Activate the virtual environment
    # On Windows:
    # venv\Scripts\activate
    # On macOS/Linux:
    # source venv/bin/activate

    # Install the package
    pip install .
    ```
    Alternatively, if published to PyPI:
    ```bash
    pip install repo2readme
    ```

3.  **Set up API Keys**:
    Repo2Readme requires API keys for the Large Language Models (LLMs) it uses (e.g., Groq, Google GenAI). You'll be prompted to enter these keys on your first run, or you can set them as environment variables (e.g., `GROQ_API_KEY`, `GOOGLE_API_KEY`).

---

## 🚀 Usage

Repo2Readme is a command-line tool. Here's how to use it:

### Generate README from a GitHub Repository URL

To generate a `README.md` for a GitHub repository:

```bash
repo2readme --url https://github.com/owner/repo-name
```

You can also specify an output file path:

```bash
repo2readme --url https://github.com/owner/repo-name --output my_project_readme.md
```

### Generate README from a Local Repository

To generate a `README.md` for a local project folder:

```bash
repo2readme --local /path/to/your/local/repository
```

Similarly, you can specify an output file path:

```bash
repo2readme --local /path/to/your/local/repository --output local_project_docs.md
```

### Reset Stored API Keys

If you need to clear your previously stored API keys, use the `reset` command:

```bash
repo2readme reset
```

---

## 🔑 Configuration / Environment Variables

Repo2Readme manages API keys necessary for interacting with LLM services. These keys are stored securely (typically in a local JSON file managed by the `config.py` module) and are not committed to version control.

The `repo2readme/config.py` module handles:
*   `load_env()`: Loads environment variables from a JSON file.
*   `save_env()`: Saves environment variables to a JSON file.
*   `get_api_keys()`: Retrieves API keys, prompting the user if they are not found.
*   `reset_api_keys()`: Deletes the stored environment variables file, effectively clearing all API keys.

You can set API keys as environment variables directly (e.g., `export GROQ_API_KEY="your_key_here"`) or let the tool prompt you on the first run.

---

## 💡 How the Code Works

Repo2Readme operates through a series of modular components to achieve its goal of generating comprehensive READMEs:

1.  **CLI Entry Point (`repo2readme/cli/main.py`)**:
    This is the main entry point for the `repo2readme` CLI. It uses the `Click` library to define commands like `run` (for generating READMEs from URLs or local paths) and `reset` (for clearing API keys). It orchestrates the flow by calling other modules to load repositories, summarize files, and generate the final README.

2.  **Configuration Management (`repo2readme/config.py`)**:
    This module is responsible for managing API keys required for LLM interactions. It provides functions to load, save, retrieve, and reset these keys, ensuring that sensitive information is handled properly and not hardcoded.

3.  **Repository Loading (`repo2readme/loaders/loader.py`, `repo2readme/loaders/repo_loader.py`)**:
    The `repo2readme/loaders/repo_loader.py` file defines classes like `LocalRepoLoader` and `UrlRepoLoader` to handle different repository sources. `LocalRepoLoader` loads files from a specified local folder path, while `UrlRepoLoader` clones a repository from a given URL (with branch support) into a temporary directory and cleans it up afterward. The `repo2readme/loaders/loader.py` acts as a facade, providing a unified `RepoLoader` class that intelligently dispatches to the correct specific loader based on the source type (URL or local path). These loaders utilize `langchain_community.document_loaders` for efficient document processing.

4.  **Utility Functions (`repo2readme/utils/`)**:
    *   **Language Detection (`detect_language.py`)**: Detects the programming language of a file based on its extension, crucial for language-specific summarization.
    *   **File Filtering (`filter.py`)**: Contains `github_file_filter` to exclude irrelevant files (e.g., binary files, large data files) from the analysis, ensuring focus on source code and documentation.
    *   **Force Removal (`force_remove.py`)**: Provides a utility `force_remove` to handle and delete read-only files, particularly useful for cleaning up cloned repositories on certain file systems.
    *   **Tree Generation (`tree.py`)**: Generates a textual tree structure of the repository directory and extracts all relevant file paths, providing a visual and structured overview of the project.

5.  **Summarization (`repo2readme/summerize/schema.py`, `repo2readme/summerize/summary.py`)**:
    *   **Schema Definition (`schema.py`)**: This file defines data processing schemas, likely using `Pydantic` and `langchain_core.output_parsers`, to structure and validate the output of the summarization process, ensuring consistent data handling.
    *   **File Summarization (`summary.py`)**: The `create_summarizer` and `summarize_file` functions in this module leverage `langchain_groq` and `langchain_core.prompts` to create concise summaries of individual files. It takes into account the file path, language, and content to generate meaningful descriptions.

6.  **README Generation (`repo2readme/readme/readme_generator.py`)**:
    This is the core module for constructing the final `README.md`. The `readme_builder` and `generate_readme` functions take the collected file summaries, the repository tree structure, and file paths as input. It uses `langchain_groq`, `langchain_google_genai`, `langchain_core.prompts`, and `langchain_core.output_parsers` to intelligently assemble these pieces into a clean, polished, and professional `README.md` document, following best practices for project documentation.

---

## 🤝 Contributing

We welcome contributions to Repo2Readme! If you have suggestions for improvements, new features, or bug fixes, please feel free to:

1.  **Fork the repository.**
2.  **Create a new branch** for your feature or bug fix.
3.  **Make your changes**, ensuring they adhere to the project's coding style.
4.  **Write clear and concise commit messages.**
5.  **Submit a pull request** with a detailed description of your changes.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

The MIT License grants permission to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, provided that the above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## 🙏 Credits / Acknowledgements

-   Developed by Sarowar Jahan Biswas.
-   Special thanks to the open-source community and the       
developers of `Click`, `Rich`, `LangChain`, `Pydantic`,       
`GitPython`, and other libraries that made this project       
possible.