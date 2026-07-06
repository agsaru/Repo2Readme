# repo2readme

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![PyPI](https://img.shields.io/pypi/v/repo2readme)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/repo2readme?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/repo2readme)

Generate high-quality, AI-powered `README.md` files from GitHub or local repositories with a single command.

This tool analyzes your project structure and source files, summarizes them using AI, and automatically generates a comprehensive, well-structured, and professional `README.md`.

## 🌟 Table of Contents

* [About the Project](#about-the-project)
* [Tech Stack](#tech-stack)
* [Key Features](#key-features)
* [Folder Structure](#folder-structure)
* [Installation](#installation)
* [Quick Start](#quick-start)
* [Usage](#usage)
* [Configuration](#configuration)
* [How It Works](#how-it-works)
* [Frequently Asked Questions](#frequently-asked-questions)
* [Troubleshooting](#troubleshooting)
* [Contributing](#contributing)
* [License](#license)

## ✨ Demo

Generate a README from GitHub:

```bash
repo2readme run --url https://github.com/agsaru/repo2readme
```

Generate a README from a local project:

```bash
repo2readme run --local ./my-project
```

## About the Project

`repo2readme` is a command-line interface (CLI) tool designed to       
automate the creation of high-quality `README.md` files. It
intelligently scans your repository, summarizes key files, and then    
iteratively generates and refines a `README` using advanced AI agents. 
Whether your project is hosted on GitHub or resides locally,
`repo2readme` streamlines documentation, ensuring your projects are    
well-explained and easily understood.

## Why Repo2Readme?

- 🤖 AI-powered README generation
- 📂 Works with both GitHub and local repositories
- ⚡ Fast file summarization using Groq
- ✨ Iterative README refinement using Gemini
- 🛠️ Simple CLI with minimal setup

## Tech Stack

The `repo2readme` project leverages a modern Python ecosystem for its  
functionality:

*   🐍 Python (>=3.10)
*   🛠️ Setuptools
*   🖱️ Click: For building intuitive command-line interfaces.
*   ✨ Rich: For beautiful terminal output and progress displays.      
*   ⚙️ GitPython: For programmatic interaction with Git repositories.  
*   🔑 python-dotenv: For managing environment variables.
*   🦜 LangChain: A framework for developing applications powered by   
language models.
*   🌍 LangChain Community: Community integrations for LangChain.      
*   🧠 LangChain Groq: Integration for Groq language models.
*   📚 LangChain Google GenAI: Integration for Google Generative AI    
models.
*   💨 Groq: For fast inference with language models (specifically     
`openai/gpt-oss-120b` for summarization).
*   🚀 Google GenAI: For accessing Google Gemini models
(`gemini-2.5-flash` for README generation and review).
*   Pydantic: For data validation and settings management (used in     
reviewer agent schema).
*   os, json, tempfile, shutil, stat, operator, typing: Standard Python
libraries for system interactions, data handling, and type hinting.    

## Key Features

*   **Repository Analysis**: Automatically loads files and content from
GitHub URLs or local directories.
*   **Intelligent Summarization**: Uses a Groq LLM to summarize        
individual source files, capturing their purpose and functionality.    
*   **Hierarchical Tree Generation**: Creates a visual representation  
of your repository's directory structure.
*   **AI-Powered README Creation**: Employs a Google Gemini model to   
draft comprehensive and structured `README.md` content.
*   **Iterative Refinement**: Utilizes an agent-based workflow with a  
reviewer agent (Google Gemini) to iteratively score and improve the    
generated README until a high-quality standard is met.
*   **API Key Management**: Securely stores and manages API keys for   
Groq and Google Gemini services in your local environment.
*   **File Filtering**: Automatically ignores common development       
artifacts (`.git`, `node_modules`, `__pycache__`, etc.) to focus on    
relevant project files.

## Folder Structure

```
Repo2Readme/
    ├── LICENSE
    ├── pyproject.toml
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
        ├── summarize/
            ├── summary.py
        ├── utils/
            ├── detect_language.py
            ├── filter.py
            ├── force_remove.py
            ├── tree.py
```

## Installation

To install `repo2readme`, you need Python 3.10 or higher.

1.  **Clone the repository (optional, if installing from source):**    
    ```bash
    git clone https://github.com/agsaru/repo2readme.git
    cd repo2readme
    ```

2.  **Install the package:**
    ```bash
    pip install repo2readme
    ```

## 🚀 Quick Start

Get started with Repo2Readme in just a few steps.

### Install

```bash
pip install -U repo2readme
```

### Generate a README from a GitHub Repository

```bash
repo2readme run --url https://github.com/agsaru/repo2readme
```

### Generate a README from a local Repository

```bash
repo2readme run --local ./my-project
```

The generated README will be saved as `README.md` unless another output file is specified.

## Usage

`repo2readme` provides two main commands: `run` to generate a README   
and `reset` to clear your stored API keys.

### 1. Generate a README

Use the `run` command with either a GitHub repository URL or a local   
path.

**From a GitHub Repository URL:**
```bash
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md
```

**From a Local Repository Path:**
```bash
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

**Options:**
*   `-u`, `--url <URL>`: GitHub repository URL to process.
*   `-l`, `--local <PATH>`: Path to a local repository.
*   `-o`, `--output <FILE_PATH>`: File path to save the generated README (defaults to `README.md`).
*   `-f`, `--force`: Overwrite the output file and bypass the token estimation confirmation prompt without confirmation.
*   `--dry-run`: Preview the analysis without making any API calls (runs local analysis, generates the repository tree, estimates token count, and prints the list of files to be processed).

### 🛡️ Token Estimation and Warnings

Running the tool on a repository can consume a significant number of LLM API tokens. To prevent accidental quota exhaustion and unexpected costs:

1. **Before any API calls are made**, `repo2readme` estimates the number of files, token count, and total request size.
2. If running interactively, the tool displays this analysis and prompts the user for confirmation:
   ```
   Repository Analysis

   Files to summarize : 45
   Estimated tokens   : ~120,000
   Request size       : ~420.5 KB

   Proceed? [y/N]
   ```
3. If confirmed, the tool retrieves API keys and begins summarization. Otherwise, it exits gracefully.
4. If `--force` is used, the confirmation prompt is automatically bypassed.

### 🔍 Dry Run Mode

You can run `repo2readme` in `--dry-run` mode to preview the analysis, view the estimated tokens, and verify your include/exclude filters without making any LLM requests or requiring API keys:

```bash
repo2readme run --local ./path/to/your/repo --dry-run
```

Output example:
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

### 2. Reset API Keys

To clear your stored Groq and Google Gemini API keys:
```bash
repo2readme reset
```
This will delete the configuration file storing your keys, prompting   
you to re-enter them on the next `run` command.

## Configuration

`repo2readme` requires API keys for Groq and Google Gemini to interact 
with large language models. These keys can be provided either as       
environment variables or will be prompted for and saved locally.       

### API Keys

*   **GROQ_API_KEY**: Required for accessing the Groq LLM (used for    
file summarization).
*   **GOOGLE_API_KEY**: Required for accessing Google Generative AI    
(Gemini) models (used for README generation and review).

When `repo2readme run` is executed for the first time or if keys are   
missing, the CLI will interactively prompt you to enter them. These    
keys are then saved in a JSON file at `~/.repo2readme_env.json` for    
future use.

Alternatively, you can set these as system environment variables:      
```bash
export GROQ_API_KEY="your_groq_api_key"
export GOOGLE_API_KEY="your_google_api_key"
```
### Verify API Keys

Before running Repo2Readme, ensure both `GROQ_API_KEY` and `GOOGLE_API_KEY` are configured correctly. Missing or invalid API keys may prevent successful README generation.

## How It Works

The `repo2readme` tool orchestrates a sophisticated workflow to        
generate a README:

1.  **Repository Loading**:
    *   Based on your input (GitHub URL or local path), a `RepoLoader` 
determines whether to use a `UrlRepoLoader` (which clones the GitHub   
repository into a temporary directory) or a `LocalRepoLoader` (which   
reads from your local filesystem).
    *   During loading, an intelligent filter (`github_file_filter`) is
applied to ignore irrelevant files and directories (e.g., `.git`,      
`node_modules`, `package-lock.json`, `.env`, various binary or data    
files), focusing only on source code and essential project files.      

2.  **Repository Structure & File Analysis**:
    *   A visual directory tree (`generate_tree`) is constructed,      
providing a clear overview of the project's structure.
    *   For each relevant file, its programming language is detected   
(`detect_lang`) based on its extension.
    *   A `summarize_file` function is then invoked, which uses a      
specialized LangChain chain powered by the **Groq LLM
(openai/gpt-oss-120b)** to generate a concise, JSON-formatted summary  
of the file's content and purpose. This summary is tailored for README 
generation.

3.  **Iterative README Generation Workflow**:
    *   The core of the README creation is handled by a **LangGraph    
state machine**. This machine iteratively generates, reviews, and      
refines the README.
    *   **Generation Node**: The `generate_readme_node` utilizes a     
**Google Gemini 2.5 Flash model** via LangChain. It takes all file     
summaries, the repository tree structure, any previous `README` 
content, and reviewer feedback to produce a new `README.md` draft.     
    *   **Review Node**: The `readme_reviewer_node` also uses a        
**Google Gemini 2.5 Flash model**. This agent evaluates the latest     
README draft, assigns it a quality score (1-10), and provides
constructive feedback for improvement.
    *   **Conditional Loop**: The workflow continues looping between   
generation and review. The process stops when the generated `README`   
achieves a score of 8.5 or higher, or if a maximum number of iterations
is reached, ensuring a high-quality output while preventing infinite   
loops.

4.  **Output**:
    *   The best-scoring `README.md` generated during the iterative    
process is selected.
    *   This final `README` content is then either printed to the      
console or saved to the specified output file (defaulting to
`README.md`).

Throughout this process, `repo2readme/config.py` manages the secure    
loading and saving of API keys, prompting the user for input if        
necessary. Temporary directories created during remote repository      
cloning are also safely cleaned up using `force_remove`.

### Configurable File Filtering

Repo2Readme uses default filters to skip generated files, build artifacts, lock files, images, archives, and other files that are usually not useful for README generation.

You can include or exclude additional files using glob patterns:

```bash
repo2readme run --local ./my-project --include "package.json"
repo2readme run --local ./my-project --exclude "tests/*"
repo2readme run --local ./my-project --include "*.json" --max-file-size-kb 200
```
...

## ❓ Frequently Asked Questions

### Does Repo2Readme support local repositories?

Yes. Repo2Readme supports both local repositories and GitHub repositories.

### Are API keys required?

Yes. Google Gemini and Groq API keys are required.

### Can I preview the analysis without using API credits?

Yes.

```bash
repo2readme run --local ./my-project --dry-run
```

### Which Python version is required?

Python 3.10 or later.

## 🛠 Troubleshooting

### Command not found

Ensure Repo2Readme is installed correctly.

```bash
pip install repo2readme
```

### Invalid API Key

Verify that your `GROQ_API_KEY` and `GOOGLE_API_KEY` are valid and configured correctly.

### Repository not found

Ensure the GitHub URL or local repository path is correct.

### Permission denied

Ensure you have permission to access the repository.

## 🚀 Roadmap

- [x] GitHub repository support
- [x] Local repository support
- [x] AI-powered README generation
- [x] Dry-run mode
- [ ] Multi-language README generation
- [ ] Custom README templates
- [ ] GitLab support

## Contributing

Contributions are welcome! Whether you're fixing bugs, improving documentation, or adding new features, your help is appreciated.

Before contributing, please read our [Contributing Guide](CONTRIBUTING.md) for details on setting up the project, coding standards, and the pull request process.

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

### Development Setup

To contribute to Repo2Readme:

1. Fork the repository.
2. Clone your fork locally.
3. Install the required dependencies.
4. Create a new feature branch.
5. Make your changes.
6. Test your changes locally.
7. Submit a Pull Request.

### Running Tests

Before submitting a Pull Request, ensure that all tests pass.

```bash
pytest
```

If additional testing tools are introduced in the future, contributors should run them before opening a Pull Request.

## License

This project is licensed under the MIT License.

Copyright (c) 2025 Sarowar Jahan Biswas

Permission is hereby granted, free of charge, to any person obtaining a
copy
of this software and associated documentation files (the "Software"),  
to deal
in the Software without restriction, including without limitation the  
rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or   
sell
copies of the Software, and to permit persons to whom the Software is  
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS 
IN THE
SOFTWARE.
