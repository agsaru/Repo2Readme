# Troubleshooting

## "Missing API key" or repeated key prompts

Your keys may not be saved correctly. Try setting them as environment variables instead:

```bash
export GROQ_API_KEY="your_groq_api_key"
export GOOGLE_API_KEY="your_google_api_key"
```

Or reset and re-enter them:

```bash
repo2readme reset
repo2readme run --local ./my-project
```

## Command not found: repo2readme

Make sure the package installed correctly and your Python scripts directory is on your `PATH`:

```bash
pip install repo2readme
python -m repo2readme --help
```

## Token estimate looks too high / request is too large

Use `--dry-run` first to check exactly which files will be sent, then narrow things down with `--exclude` or `--max-file-size-kb`:

```bash
repo2readme run --local ./my-project --dry-run
repo2readme run --local ./my-project --exclude "tests/*" --max-file-size-kb 100
```

## Generated README looks incomplete or low quality

The tool iterates internally until the reviewer agent scores the draft 8.5+ or a max iteration count is hit. If quality is still off, check that your repo's key files (entry points, config, core logic) aren't being filtered out — run with `--dry-run` to confirm they're in the "Files to be processed" list.

## Errors cloning a GitHub URL

Confirm the repository is public (or that you have access), and that the URL is a valid `https://github.com/<owner>/<repo>` link.

## Still stuck?

Open an issue: https://github.com/agsaru/Repo2Readme/issues
