
# Repo2Readme

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

Repo2Readme is a powerful Python-based command-line interface 
(CLI) tool designed to effortlessly generate clean, polished, 
and professional `README.md` files. Whether you're working    
with a GitHub repository or a local project, Repo2Readme      
streamlines documentation by automatically summarizing code   
and structuring the project information.

This tool aims to simplify the often tedious task of creating 
comprehensive READMEs, allowing developers to focus more on   
coding and less on manual documentation.

## 📖 Table of Contents

- [✨ Key Features](#-key-features)
- [🚀 Tech Stack](#-tech-stack)
- [📁 Folder Structure](#-folder-structure)
- [⚙️ Installation](#️-installation)
- [💡 Configuration](#-configuration)
- [▶️ Usage](#️-usage)
- [🧠 How the Code Works](#-how-the-code-works)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- (#-credits--acknowledgements)

## ✨ Key Features

Repo2Readme provides a robust set of features to automate and 
enhance your README generation process:

-   **🌐 GitHub Repository Support**: Generate `README.md`    
files directly from any public GitHub repository URL.
-   **💻 Local Repository Support**: Create `README.md` files 
for projects hosted on your local machine.
-   **🔍 Intelligent Code Summarization**: Utilizes Language  
Models (LLMs) to generate structured JSON summaries of        
individual files.
-   **🌳 Automatic Folder Structure Generation**: Visualizes  
your project's directory hierarchy as a clear, readable tree  
structure.
-   **🗣️ Language Detection**: Automatically detects the      
programming language of files to inform summarization.        
-   **🧹 File Filtering**: Selectively include or exclude     
files from the analysis to focus on relevant code.
-   **🛡️ API Key Management**: Securely manage and reset API  
keys for LLM services.
-   **📝 Professional README Output**: Generates a clean,     
polished, and well-structured `README.md` file, ready for     
publishing.

## 🚀 Tech Stack

Repo2Readme is built with a modern Python tech stack,
leveraging powerful libraries for robust functionality:       

-   **Python** 🐍: The core programming language.
-   **Click** ⚡: For building the intuitive command-line     
interface.
-   **Rich** ✨: For beautiful terminal output and enhanced   
user experience.
-   **Pydantic** ✅: For data validation and settings
management, especially for schema definitions.
-   **LangChain** 🔗: Provides the framework for interacting  
with Language Models.
    -   **`langchain-groq`**: Integration with Groq for       
high-performance LLM inference.
    -   **`langchain-google-genai`**: Integration with        
Google's Generative AI models.
    -   **`langchain-community`**: For document loaders and   
other community-contributed components.
    -   **`langchain-core`**: Core components for prompts,    
output parsers, etc.
-   **python-dotenv** ⚙️: For loading environment variables   
from `.env` files.
-   **GitPython** 🐙: For interacting with Git repositories   
programmatically.
-   **os, json, tempfile, shutil, stat, typing** 🛠️: Standard 
Python libraries for file system operations, data handling,   
and type hinting.

## 📁 Folder Structure

The repository follows a clear and organized structure:       

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
    └── repo2readme.egg-info/
        └── PKG-INFO
```

## ⚙️ Installation

To get started with Repo2Readme, follow these simple steps:   

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/Repo2Readme.git
    cd Repo2Readme
    ```

2.  **Install dependencies:**

    It is recommended to use a virtual environment.

    Using `poetry` (recommended, as `pyproject.toml` is       
present):

    ```bash
    poetry install
    poetry shell
    ```

    Alternatively, using `pip`:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows:
venv\Scripts\activate
    pip install -e .
    ```

## 💡 Configuration

Repo2Readme requires API keys for Language Model (LLM)        
services to function. These are managed via environment       
variables.

1.  **Create a `.env` file:**
    In the root directory of the project, create a file named 
`.env`.

2.  **Add your API keys:**
    Populate the `.env` file with your Google Generative AI   
API key (e.g., for Gemini) and/or Groq API key.

    ```
    GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
    GROQ_API_KEY="YOUR_GROQ_API_KEY"
    ```

    You can obtain these keys from the respective provider's  
developer console.

3.  **Reset API Keys (if needed):**
    If you need to clear your stored API keys or encounter    
issues, you can use the `reset` command:

    ```bash
    repo2readme reset
    ```

    This will delete the environment variables file, prompting
you to re-enter keys on the next run if not provided via      
`.env`.

## ▶️ Usage

Repo2Readme is a command-line tool. Here's how to use it:     

### Generate README for a GitHub Repository

To generate a `README.md` for a GitHub repository, provide its
URL:

```bash
repo2readme run --url https://github.com/owner/repository     
--output README.md
```

-   `--url <github-url>`: The URL of the GitHub repository.   
-   `--output <file-path>`: (Optional) The path to save the   
generated README file. Defaults to `README.md` in the current 
directory.

### Generate README for a Local Repository

To generate a `README.md` for a local repository, provide the 
path to its directory:

```bash
repo2readme run --local /path/to/your/local/repo --output     
README.md
```

-   `--local <path-to-repo>`: The path to your local
repository.
-   `--output <file-path>`: (Optional) The path to save the   
generated README file. Defaults to `README.md` in the current 
directory.

### Reset API Keys

If you need to clear your stored API keys:

```bash
repo2readme reset
```

## 🧠 How the Code Works

Repo2Readme operates through a series of modular components,  
orchestrated to fetch repository data, analyze code, and      
construct a comprehensive `README.md`.

1.  **Entry Point (`repo2readme/cli/main.py`)**:
    The `main.py` script serves as the command-line
interface's entry point, defining the `run` and `reset`       
commands using `click`. It orchestrates the entire process,   
from loading repositories to generating the final README.     

2.  **Configuration and API Key Management
(`repo2readme/config.py`)**:
    The `config.py` file is responsible for managing API keys.
It handles loading environment variables from a JSON file (or 
prompting the user for input) and saving them. The
`get_api_keys` function retrieves necessary credentials, while
`reset_api_keys` allows for clearing stored keys.

3.  **Repository Loading (`repo2readme/loaders/loader.py`,    
`repo2readme/loaders/repo_loader.py`)**:
    The `loader.py` and `repo_loader.py` modules are designed 
to load documents from both local and remote repositories.    
`RepoLoader` acts as a facade, delegating to `UrlRepoLoader`  
for GitHub URLs or `LocalRepoLoader` for local paths. These   
loaders handle fetching repository content, preparing it for  
analysis, and performing necessary cleanup operations (e.g.,  
removing temporary directories).

4.  **Utility Functions (`repo2readme/utils/`)**:
    This directory contains several helper utilities:
    *   **`detect_language.py`**: The `detect_lang` function  
identifies the programming language of a file based on its    
extension, crucial for accurate summarization.
    *   **`filter.py`**: Provides the `github_file_filter`    
function, which allows for selectively including or excluding 
files from the analysis, ensuring only relevant content is    
processed.
    *   **`force_remove.py`**: The `force_remove` function    
handles file system cleanup by forcing read-only files to be  
writable before removal, preventing permission errors during  
temporary directory cleanup.
    *   **`tree.py`**: Contains `generate_tree` to create a   
visual string representation of the directory structure and   
`extract_tree` to parse the repository's file hierarchy,      
returning both the tree string and a list of file paths.      

5.  **Summarization (`repo2readme/summerize/schema.py`,       
`repo2readme/summerize/summary.py`)**:
    *   **`schema.py`**: Defines the data processing schema,  
likely using Pydantic, to structure the output of file        
summaries into a consistent format (`CodeSummary`,
`FunctionSummary`, `Param`).
    *   **`summary.py`**: Implements `create_summarizer` to   
initialize a Language Model (LLM) and `summarize_file` to     
generate structured JSON summaries of individual files. This  
involves sending file content and language information to the 
LLM and parsing its output according to the defined schema.   

6.  **README Generation
(`repo2readme/readme/readme_generator.py`)**:
    The `readme_generator.py` module is responsible for       
assembling the final `README.md` file. It uses the
`readme_builder` function to combine the gathered file        
summaries, the repository's tree structure, and file paths    
into a coherent and professional Markdown document. The       
`generate_readme` function orchestrates this process,
producing the complete README.

In essence, Repo2Readme downloads or accesses a repository,   
maps its structure, intelligently summarizes its constituent  
files using LLMs, and then synthesizes all this information   
into a well-organized and informative `README.md`.

## 🤝 Contributing

We welcome contributions to Repo2Readme! If you have
suggestions for improvements, bug reports, or want to
contribute code, please feel free to:

1.  **Fork the repository**.
2.  **Create a new branch** for your feature or bug fix.      
3.  **Make your changes** and ensure they adhere to the       
project's coding style.
4.  **Write clear, concise commit messages**.
5.  **Submit a pull request** with a detailed description of  
your changes.

## 📄 License

This project is licensed under the MIT License.

```
MIT License

Copyright (c) 2025 Sarowar Jahan Biswas

Permission is hereby granted, free of charge, to any person   
obtaining a copy
of this software and associated documentation files (the      
"Software"), to deal
in the Software without restriction, including without        
limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, 
and/or sell
copies of the Software, and to permit persons to whom the     
Software is
furnished to do so, subject to the following conditions:      

The above copyright notice and this permission notice shall be
included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY     
KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF       
MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO   
EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES 
OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
DEALINGS IN THE
SOFTWARE.
```

## 🙏 Credits & Acknowledgements

-   Developed by Sarowar Jahan Biswas.
-   Special thanks to the open-source community and the       
developers of `Click`, `Rich`, `LangChain`, `Pydantic`,       
`GitPython`, and other libraries that made this project       
possible.