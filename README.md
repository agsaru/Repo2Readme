# 🚀 Repo2Readme

## Generate High-Quality READMEs for Your Repositories with AI

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.1.0-green?style=for-the-badge)
![Click](https://img.shields.io/badge/Click-4179C2?style=for-the-badge&logo=click&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![MIT License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)

Repo2Readme is a powerful Python-based command-line interface (CLI) tool designed to effortlessly generate clean, polished, and professional `README.md` files for any GitHub or local repository. Leveraging advanced language models, it intelligently summarizes code, detects languages, and extracts repository structures to create comprehensive documentation, saving developers valuable time.

Whether you're starting a new project or need to document an existing one, Repo2Readme streamlines the process, ensuring your projects are well-explained and accessible.

## 📝 Table of Contents

*   [🚀 Features](#-features)
*   [🛠️ Tech Stack](#%EF%B8%8F-tech-stack)
*   [📂 Folder Structure](#-folder-structure)
*   [⚙️ Installation](#%EF%B8%8F-installation)
*   [💡 Usage](#-usage)
*   [🔑 Configuration / Environment Variables](#-configuration--environment-variables)
*   [🧠 How the Code Works](#-how-the-code-works)
*   [🤝 Contributing](#-contributing)
*   [📄 License](#-license)
*   [🙏 Credits / Acknowledgements](#-credits--acknowledgements)

## 🚀 Features

Repo2Readme offers a range of features to automate and enhance your repository documentation:

*   **⚡ Automated README Generation**: Generates high-quality `README.md` files for both public GitHub repositories and local project folders.
*   **🤖 AI-Powered Code Summarization**: Utilizes Language Models (LLMs) to summarize code files, functions, classes, and components, extracting key information.
*   **🌐 Language Detection**: Automatically detects the programming language of files within the repository to provide accurate context.
*   **🌳 Repository Tree Extraction**: Visualizes and extracts the hierarchical structure of your repository, including file paths.
*   **✨ Structured Output**: Employs Pydantic schemas to ensure LLM outputs for code summaries are consistent and well-structured.
*   **🖥️ User-Friendly CLI**: Built with `Click` and `Rich` for an intuitive and visually appealing command-line experience.

## 🛠️ Tech Stack

This project is built using the following technologies:

*   **Python**: 🐍 The core programming language for the entire application.
*   **LangChain**: 🦜 Framework for developing applications powered by language models, used for orchestrating summarization and README generation.
*   **Click**: ⚡ A Python package for creating beautiful command-line interfaces.
*   **Rich**: 🌈 A Python library for rich text and beautiful formatting in the terminal.
*   **Pydantic**: ✅ Data validation and settings management using Python type hints, crucial for defining structured data schemas.
*   **Groq**: 🚀 (via `langchain-groq`) Used as a fast inference provider for language models.
*   **Google GenAI**: 🧠 (via `langchain-google-genai`) Integration for Google's Generative AI models.
*   **python-dotenv**: 🔐 Manages environment variables for API keys and configurations.
*   **GitPython**: 📦 (Implicitly used via `langchain-community` loaders) A Python library to interact with Git repositories.

## 📂 Folder Structure

```
./
├── .gitignore
├── LICENSE
├── pyproject.toml
├── README.md
├── repo2readme/
│   ├── cli/
│   │   └── main.py
│   ├── loaders/
│   │   ├── loader.py
│   │   └── repo_loader.py
│   ├── readme/
│   │   └── readme_generator.py
│   ├── summerize/
│   │   ├── schema.py
│   │   └── summary_chain.py
│   ├── utils/
│   │   ├── detect_language.py
│   │   ├── filter.py
│   │   ├── force_remove.py
│   │   └── tree.py
└── repo2readme.egg-info/
    └── PKG-INFO
```

## ⚙️ Installation

To get started with Repo2Readme, follow these simple steps:

1.  **Clone the repository (if not already local):**
    ```bash
    git clone https://github.com/your-username/repo2readme.git
    cd repo2readme
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    # On macOS/Linux
    source .venv/bin/activate
    # On Windows
    .venv\Scripts\activate
    ```

3.  **Install the project in editable mode with its dependencies:**
    ```bash
    pip install -e .
    ```

## 💡 Usage

Repo2Readme provides a straightforward command-line interface.

### Generate README for a GitHub Repository

To generate a README for a public GitHub repository, provide its URL:

```bash
repo2readme --url https://github.com/owner/repository-name --output README.md
```

*   `--url <repository_url>`: The URL of the GitHub repository.
*   `--output <file_path>`: (Optional) Path to save the generated README file. Defaults to `README.md` in the current directory.

### Generate README for a Local Repository

To generate a README for a local repository on your machine:

```bash
repo2readme --local /path/to/your/local/repo --output MY_PROJECT_README.md
```

*   `--local <local_path>`: The file path to your local repository.
*   `--output <file_path>`: (Optional) Path to save the generated README file.

## 🔑 Configuration / Environment Variables

Repo2Readme uses environment variables to configure API keys for language models (e.g., Groq, Google GenAI).

Create a `.env` file in the root of your project directory (where you run the `repo2readme` command) and add your API keys:

```dotenv
GROQ_API_KEY="your_groq_api_key_here"
GOOGLE_API_KEY="your_google_api_key_here"
```

These variables are loaded using `python-dotenv` to securely access the necessary services.

## 🧠 How the Code Works

Repo2Readme orchestrates a series of steps to intelligently generate a `README.md` file. Here's a breakdown of its internal workings:

1.  **CLI Entry Point (`repo2readme/cli/main.py`)**:
    *   The `main.py` script serves as the command-line interface entry point, powered by the `Click` library for parsing arguments (repository URL, local path, output file) and `Rich` for enhanced terminal output.
    *   It coordinates the entire README generation workflow, from loading the repository to writing the final file.

2.  **Repository Loading (`repo2readme/loaders/loader.py`, `repo2readme/loaders/repo_loader.py`)**:
    *   The `loader.py` module defines classes like `LocalRepoLoader` and `UrlRepoLoader` to handle fetching repository content.
    *   It contains `load` functions capable of processing either a local folder path or a remote Git clone URL, optionally specifying a branch.
    *   Utilities for `get_repo_name` and `cleanup` (to remove temporary cloned repositories) are also provided, utilizing `langchain_community.document_loaders`, `os`, `tempfile`, `shutil`, `repo2readme.utils.filter`, and `repo2readme.utils.force_remove`.

3.  **Utility Functions (`repo2readme/utils/`)**:
    *   **`detect_language.py`**: The `detect_lang` function identifies the programming language of a given file path, crucial for context-aware summarization.
    *   **`filter.py`**: The `github_file_filter` function helps in selectively including or excluding files from the analysis, ensuring only relevant code is processed.
    *   **`force_remove.py`**: This utility provides a `force_remove` function to handle file system cleanup, especially useful for dealing with permissions issues during temporary directory removal by `GitLoader`.
    *   **`tree.py`**: Contains `generate_tree` to create a visual string representation of the directory structure and `extract_tree` to parse the repository's file hierarchy and return a tuple of the tree string and a list of file paths.

4.  **Code Summarization (`repo2readme/summerize/schema.py`, `repo2readme/summerize/summary_chain.py`)**:
    *   **`schema.py`**: This file defines the Pydantic data models (`Param`, `FunctionSummary`, `CodeSummary`) used to structure the output of the LLM-based summarization. `CodeSummary` is the central model, capturing the file path, language, a short description, detected functions/classes, imports, and exports. It includes robust `field_validator` methods to normalize messy LLM outputs into consistent formats.
    *   **`summary_chain.py`**: The `create_summarizer` and `summarize_file` functions are responsible for taking a file's content, language, and path, and using a Language Model (e.g., via `langchain_groq`) to generate a structured JSON summary that strictly adheres to the `CodeSummary` schema. It imports `langchain_core.prompts` and utilizes `dotenv` for configuration.

5.  **README Generation (`repo2readme/readme/readme_generator.py`)**:
    *   The `readme_builder` and `generate_readme` functions take the comprehensive list of `CodeSummary` objects (one for each file), the extracted repository tree structure, and the list of file paths.
    *   These functions then employ additional Language Models (e.g., `langchain_groq`, `langchain_google_genai`) and sophisticated prompting techniques to synthesize all the gathered information into a coherent, well-structured, and professional `README.md` file. It leverages `langchain_core.prompts` and `langchain_core.output_parsers`.

6.  **Project Metadata**:
    *   **`.gitignore`**: Specifies files and directories that Git should ignore.
    *   **`LICENSE`**: Details the MIT License under which the software is distributed, granting broad permissions for use, modification, and distribution.
    *   **`pyproject.toml`**: Standard Python project configuration file, defining project metadata and build system requirements, including the entry point for the CLI (`repo2readme.cli.main`).
    *   **`repo2readme.egg-info/PKG-INFO`**: Contains metadata about the package, generated during installation.

The overall flow begins with the CLI, which loads the repository, processes each relevant file through language detection and summarization, gathers the repository structure, and finally uses an LLM to weave all this information into a complete `README.md`.

## 🤝 Contributing

We welcome contributions to Repo2Readme! If you have suggestions, bug reports, or want to contribute code, please feel free to:

1.  **Fork** the repository.
2.  **Create a new branch** (`git checkout -b feature/your-feature-name`).
3.  **Make your changes** and commit them (`git commit -m 'feat: Add new feature'`).
4.  **Push** to your branch (`git push origin feature/your-feature-name`).
5.  **Open a Pull Request** to the `main` branch.

Please ensure your code adheres to the existing style and conventions.

## 📄 License

This project is licensed under the MIT License.

```
MIT License

Copyright (c) [Year] [Your Name or Project Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🙏 Credits / Acknowledgements

*   **LangChain**: For providing the powerful framework for LLM integrations.
*   **Click** and **Rich**: For enabling a delightful command-line experience.
*   **Pydantic**: For robust data validation and schema definition.
*   **Groq** and **Google GenAI**: For providing the underlying language models.
*   The open-source community for their invaluable tools and inspiration.