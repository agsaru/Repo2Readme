# CLI Reference

## `repo2readme run`

Generates a `README.md` by analyzing a repository (GitHub URL or local path).

```bash
repo2readme run [OPTIONS]
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--url <URL>` | `-u` | GitHub repository URL to process. |
| `--local <PATH>` | `-l` | Path to a local repository. |
| `--output <FILE_PATH>` | `-o` | File path to save the generated README. Defaults to `README.md`. |
| `--force` | `-f` | Overwrite the output file and skip the token estimation confirmation prompt. |
| `--respect-gitignore` | | Honor `.gitignore` and `.git/info/exclude` patterns during repository traversal. This is opt-in; default behavior is unchanged. |
| `--dry-run` | | Preview the analysis (repo tree, token estimate, files to be processed) without making any API calls or requiring API keys. |
| `--include <PATTERN>` | | Glob pattern for files to include, even if normally filtered out. Can be passed multiple times. |
| `--exclude <PATTERN>` | | Glob pattern for files to exclude. Can be passed multiple times. |
| `--max-file-size-kb <N>` | | Skip files larger than N KB. |

You must provide exactly one of `--url` or `--local`.

### `--respect-gitignore`

Honor `.gitignore` and `.git/info/exclude` patterns during repository traversal. This is opt-in, so the default behavior remains unchanged. When enabled, files and directories matching gitignore rules are skipped before language detection, parsing, summarization, and token estimation.

```bash
repo2readme run --local ./repo --respect-gitignore
repo2readme run --url https://github.com/user/repo --respect-gitignore
```

### `--dry-run`

Runs local analysis only — repo tree generation, file filtering, and token estimation — with no LLM calls and no API keys required. Useful for verifying your include/exclude filters before spending tokens.

```bash
repo2readme run --local ./path/to/your/repo --dry-run
```

Example output:

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

## `repo2readme reset`

Deletes the locally stored API key configuration file (`~/.repo2readme_env.json`).

```bash
repo2readme reset
```

You'll be prompted to re-enter your `GROQ_API_KEY` and `GOOGLE_API_KEY` on the next `run`.

## See also

- [Configuration](./configuration.md) — API keys and env vars
- [Examples](./examples.md) — real command examples
