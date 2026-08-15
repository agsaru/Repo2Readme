# Configuration

By default `repo2readme` uses two LLM providers, so it needs API keys for both:

| Variable | Used for |
|---|---|
| `GROQ_API_KEY` | File summarization (Groq's `openai/gpt-oss-120b`) |
| `GOOGLE_API_KEY` | README generation & review (Gemini `2.5-flash`) |

If you pass `--provider`, only that provider's key is needed.

## Supported providers

Run `repo2readme providers` to print this table from your installed version:

| Provider | Aliases | Default model | API key env var |
|---|---|---|---|
| `groq` | | `openai/gpt-oss-120b` | `GROQ_API_KEY` |
| `google` | `gemini` | `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| `openai` | | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `anthropic` | `claude` | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openrouter` | | `openai/gpt-4o-mini` | `OPENROUTER_API_KEY` |
| `together` | | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | `TOGETHER_API_KEY` |
| `ollama` | | `llama3` | not required (local) |

`--model` overrides the default model and `--base-url` overrides the default
endpoint. `openrouter` and `together` are reached through the OpenAI-compatible
API, so their base URLs are applied for you:

```bash
repo2readme run --local . --provider together
repo2readme run --local . --provider anthropic --model claude-sonnet-4-5
```

`ollama` talks to a local server (`http://localhost:11434` by default) and never
prompts for a key. It needs the optional `langchain-ollama` package:

```bash
pip install langchain-ollama
repo2readme run --local . --provider ollama --model llama3
```

A provider that is not in the table now fails immediately with the list of
supported names, instead of failing later during summarization.

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

You can also copy [`.env.example`](../.env.example) to `.env` in your project
root and fill in the keys there — `repo2readme` loads `.env` automatically
via `python-dotenv`.

```bash
cp .env.example .env
```

## Resetting your keys

If a key is wrong, expired, or you want to switch accounts:

```bash
repo2readme reset
```

This deletes the saved config file. You'll be prompted to re-enter keys on the next `run`.

## Where to get keys

- Groq: https://console.groq.com
- Google Gemini: https://aistudio.google.com

## README post-processing

The model's answer is not written to disk verbatim. Two things happen first.

### Normalization (applied automatically)

- A code fence wrapping the whole document is removed. Models often answer with
  ```` ```markdown ... ``` ````, which would otherwise render the entire README
  as one grey code block on GitHub.
- Trailing whitespace is stripped from every line.
- Runs of 3+ blank lines are collapsed to 2.
- Leading blank lines are removed and the file ends with exactly one newline.

Only mechanical changes are made here; nothing rewrites the model's wording.

### Validation (reported, not rewritten)

Problems that cannot be fixed without guessing at intent are logged as warnings:

| Check | Reported when |
|---|---|
| `broken-anchor` | A table-of-contents link points at a heading that does not exist. |
| `placeholder-image` | An image has an empty target, or one like `path/to/logo.png`. |
| `missing-h1` | The document has no top-level heading. |
| `duplicate-h1` | The document has more than one. |

Anchors are computed the way GitHub computes them (lowercase, punctuation and
emoji dropped, spaces to hyphens, `-1` suffixes for repeats), so the anchor
check matches what actually renders.

Everything inside fenced code blocks is ignored, so example Markdown in a usage
section is never mistaken for the document's own headings, links or images.

Run with `-v` to see these warnings if your console is configured to hide them.

## Paths in summaries and the cache

Everything the model sees, and every cache key, uses the path **relative to the
repository** — `src/api/routes.py`, never `/Users/you/work/app/src/api/routes.py`
or the temporary clone directory a `--url` run uses.

That matters for three reasons:

- The summarization prompt interpolates the path and asks the model to echo it
  back, so an absolute path ends up quoted in the generated README.
- The directory roll-up splits the path to build its tree; an absolute path
  produced one directory node per filesystem component before reaching anything
  belonging to the repository.
- Cache entries keyed on an absolute path miss as soon as the checkout moves,
  even though the content is unchanged.

The path recorded in each summary is set by `repo2readme`, not taken from the
model's answer, so a model that echoes the path back incorrectly cannot corrupt
the roll-up.

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

## Retry behaviour

Every LLM call is retried on transient failures (rate limits, timeouts, dropped
connections, malformed JSON responses) with exponential backoff and jitter.
Permanent failures — bad API key, unsupported provider, context length exceeded
— are not retried.

| Variable | Default | Meaning |
|---|---|---|
| `REPO2README_MAX_RETRIES` | `2` | Retries after the first attempt. `0` disables retrying. |
| `REPO2README_RETRY_BASE_DELAY` | `1.0` | Seconds before the first retry; doubles each attempt, capped at 30s. |

If the provider returns a `Retry-After` header, or puts a "try again in 6.7s"
hint in the error message, that value is used instead of the computed delay.
