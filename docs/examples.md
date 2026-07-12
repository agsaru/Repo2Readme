# Examples

## Generate a README for a public GitHub repo

```bash
repo2readme run --url https://github.com/agsaru/repo2readme -o README_NEW.md
```

## Generate a README for a project on your machine

```bash
repo2readme run --local ./my-project
```

## Skip the confirmation prompt and overwrite the existing README

```bash
repo2readme run --local ./my-project -o README.md --force
```

## Preview what will be processed, without using API calls

```bash
repo2readme run --local ./my-project --dry-run
```

## Include a file that's normally filtered out

```bash
repo2readme run --local ./my-project --include "package.json"
```

## Exclude a directory

```bash
repo2readme run --local ./my-project --exclude "tests/*"
```

## Combine include/exclude with a file size limit

```bash
repo2readme run --local ./my-project --include "*.json" --max-file-size-kb 200
```

## Start fresh with new API keys

```bash
repo2readme reset
repo2readme run --local ./my-project
```
