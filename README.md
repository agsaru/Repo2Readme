# repo2readme

Generate a professional `README.md` from any GitHub or local
repository. This tool analyzes your project structure and file
contents, then leverages AI models to intelligently craft a
comprehensive and informative README.

## 🌟 Table of Contents

*   [About the Project](#about-the-project)
*   [Tech Stack](#tech-stack)
*   [Key Features](#key-features)
*   [Folder Structure](#folder-structure)
*   [Installation](#installation)
*   [Usage](#usage)
*   [Configuration](#configuration)
*   [How It Works](#how-it-works)
*   [License](#license)

## About the Project

`repo2readme` is a command-line interface (CLI) tool designed to       
automate the creation of high-quality `README.md` files. It
intelligently scans your repository, summarizes key files, and then    
iteratively generates and refines a `README` using advanced AI agents. 
Whether your project is hosted on GitHub or resides locally,
`repo2readme` streamlines documentation, ensuring your projects are    
well-explained and easily understood.

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
        ├── summerize/
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

## Usage

`repo2readme` provides two main commands: `run` to generate a README   
and `reset` to clear your stored API keys.

### 1. Generate a README

Use the `run` command with either a GitHub repository URL or a local   
path.

**From a GitHub Repository URL:**
```bash
repo2readme run --url https://github.com/agsaru/repo2readme -o
README_NEW.md
```

**From a Local Repository Path:**
```bash
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

**Options:**
*   `-u`, `--url <URL>`: GitHub repository URL to process.
*   `-l`, `--local <PATH>`: Path to a local repository.
*   `-o`, `--output <FILE_PATH>`: File path to save the generated      
README (defaults to `README.md`).

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