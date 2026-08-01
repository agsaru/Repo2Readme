# Configuration

`repo2readme` uses two LLM providers under the hood, so it needs API keys for both:

| Variable | Used for |
|---|---|
| `GROQ_API_KEY` | File summarization (Groq's `openai/gpt-oss-120b`) |
| `GOOGLE_API_KEY` | README generation & review (Gemini `2.5-flash`) |

## Option 1: Let the CLI prompt you

The first time you run `repo2readme run` without keys set, the CLI will interactively ask for them and save them locally to:

```
~/.repo2readme_env.json
```

You won't need to re-enter them on future runs.

## Option 2: Set environment variables

```bash
export GROQ_API_KEY="your_groq_api_key"
export GOOGLE_API_KEY="your_google_api_key"
```

This is useful for CI pipelines or if you don't want keys persisted to disk.

## Resetting your keys

If a key is wrong, expired, or you want to switch accounts:

```bash
repo2readme reset
```

This deletes the saved config file. You'll be prompted to re-enter keys on the next `run`.

## Where to get keys

- Groq: https://console.groq.com
- Google Gemini: https://aistudio.google.com

## Summary Cache

`repo2readme` maintains a local cache of file summaries to avoid redundant API calls.

### Cache location

The cache is stored in:

```
.repo2readme/cache/summaries.json
```

This directory is created automatically in the current working directory when you run `repo2readme run`.

### How caching works

1. **First run (cache miss):** Each file is summarized via the LLM, and the result is stored in the cache along with a SHA-256 content hash, detected language, and the current summarization configuration (provider, model, prompt template hash).

2. **Subsequent runs (cache hit):** Before calling the LLM, the tool checks the cache. If a file's content hash matches the cached entry and the configuration hasn't changed, the cached summary is reused — no API call is made.

3. **Modified files:** If a file's content changes, its content hash no longer matches, so the summary is regenerated and the cache is updated.

4. **Deleted files:** Cache entries for files that no longer exist are automatically cleaned up.

### Cache invalidation

The cache is automatically invalidated when any of the following change:

- **LLM provider** (`--provider`)
- **Model name** (`--model`)
- **Base URL** (`--base-url`)
- **Prompt template** (code change to the summarization prompt)
- **Cache schema version** (internal format change)

When invalidation occurs, all existing cache entries are discarded and summaries are regenerated on the next run.

### Corruption handling

If the cache file becomes corrupted (e.g., invalid JSON), `repo2readme` logs a warning and automatically rebuilds the cache. Execution continues normally.

### Adding the cache directory to `.gitignore`

It is recommended to add the cache directory to your project's `.gitignore`:

```
.repo2readme/
```
