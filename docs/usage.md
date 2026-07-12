# Usage

`repo2readme` has two commands: `run` (generate a README) and `reset` (clear saved API keys).

## Generate a README from a GitHub repo

```bash
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md
```

## Generate a README from a local repo

```bash
repo2readme run --local ./path/to/your/repo -o README_LOCAL.md
```

If you don't pass `-o`, the output defaults to `README.md` in your current directory.

## Preview before spending tokens

Every `run` estimates token usage and file count before making any API calls, and asks for confirmation:

```
Repository Analysis

Files to summarize : 45
Estimated tokens   : ~120,000
Request size       : ~420.5 KB

Proceed? [y/N]
```

Pass `--force` to skip this prompt and overwrite the output file automatically.

To check what *would* happen without using any API calls or requiring keys at all, use `--dry-run` — see [CLI Reference](./cli-reference.md#--dry-run) for details.

## Filtering files

By default, common non-essential files (`.git`, `node_modules`, lock files, images, archives, etc.) are skipped. You can adjust this with `--include` / `--exclude` / `--max-file-size-kb` — see [Configuration](./configuration.md) and the [CLI Reference](./cli-reference.md).

## Clear stored API keys

```bash
repo2readme reset
```

## More

- [CLI Reference](./cli-reference.md) — every flag, explained
- [Examples](./examples.md) — common real-world commands
- [Troubleshooting](./troubleshooting.md) — fixing common issues
