# Configuration

`repo2readme` uses **one** provider for the whole run. With no flags that is
Groq, so one key is enough:

| Variable | Used for |
|---|---|
| `GROQ_API_KEY` | File summarization, directory roll-ups, README generation and review |

Only the providers a run actually calls are asked for, so `--provider anthropic`
needs `ANTHROPIC_API_KEY` and nothing else.

> Earlier versions summarized with Groq and reviewed with Google, so a run
> without `--provider` needed two keys from two vendors — and `--model` was
> handed to both of them, which meant `--model <a Groq model>` summarized fine
> and then died in review with a Google "model not found". The provider, model
> and base URL are now resolved once, before the repository is loaded.

## Reviewing with a different provider

The generated README is scored by a reviewer step, which by default uses the
same provider and model as everything else. To get a second opinion from
another vendor, say so explicitly:

```bash
repo2readme run --local . --provider groq --reviewer-provider google
```

| Option | Default |
|---|---|
| `--reviewer-provider` | `--provider` |
| `--reviewer-model` | `--model`, or the reviewer provider's own default model when `--reviewer-provider` names a different vendor |
| `--reviewer-base-url` | `--base-url` |

A model name belongs to the provider it was given for, so when the reviewer
runs on a *different* vendor it uses that vendor's default model rather than
inheriting `--model`. Name `--reviewer-model` to choose it yourself. Both are
printed before the work starts whenever they differ.

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

## Which files are analyzed by default

A set of built-in rules decides which files are worth sending to the model.
They are **defaults**: the CLI flags are evaluated first, in this order.

1. `--exclude` wins outright. A file matching an exclude pattern is never
   analyzed, whatever else says otherwise.
2. `--include` overrides the default rules. A file matching an include pattern
   is analyzed even if the rules below would skip it — including a `.env` file,
   if that is what you name. It still has to pass `--max-file-size-kb`.
   Lock files are the one exception: a broad pattern like `*.json` will not
   pull in `package-lock.json`; you have to name it exactly.
3. Otherwise the default rules below apply.

### Manifests are always read

Dependency, build and environment manifests are read even though their
extension (`.json`, `.txt`) is otherwise ignored, because they are what the
**Tech Stack**, **Installation** and **Environment Variables** sections of the
generated README are built from:

| Kind | Files |
|---|---|
| Python | `requirements.txt`, `requirements-*.txt`, `requirements/*.txt`, `constraints.txt`, `Pipfile` |
| JavaScript / TypeScript | `package.json`, `tsconfig.json`, `jsconfig.json`, `bower.json`, `deno.json`, `turbo.json`, `nx.json`, `lerna.json`, `angular.json`, `nest-cli.json`, `jsr.json` |
| PHP | `composer.json` |
| Environment | `.env.example`, `.env.sample`, `.env.template` |

Lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) are **not** in
this list — they are large, generated, and add nothing a manifest doesn't
already say. Real `.env` files (`.env`, `.env.local`, `.env.production`,
`.env.test`) are never read.

A manifest inside an ignored directory stays ignored, so a
`node_modules/left-pad/package.json` is not analyzed.

### Ignored directories

Two groups, because the names behave differently:

- **Ignored wherever they appear:** `node_modules`, `__pycache__`, `dist`,
  `build`, `target`, `obj`, `coverage`, `.git`, `.venv`, `.next`, `.yarn`,
  `.pnpm`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.gradle`, `.mvn`,
  `.nuget`, `.bundle`, `.cargo`, `.firebase`, `.idea`, `.vscode`, `.cache`,
  `bower_components`.
- **Ignored only at the repository root:** `bin`, `env`, `venv`, `vendor`,
  `public`, `logs`, `out`. Nested, these are ordinary source directories —
  `src/bin/run.py` and `app/public/routes.rb` are analyzed normally.

`pkg/` and `packages/` are not ignored at all: in a checked-out repository they
are the standard Go project layout and a JavaScript monorepo's workspace root.

### Environment files

Every `.env*` file is skipped by default — not only the common names, but
`.env.staging`, `.env.prod`, `.env.development.local`, `.envrc` and anything
else in the family — because they hold real credentials. The three checked-in
templates (`.env.example`, `.env.sample`, `.env.template`) are the exception,
since they exist to document variable *names*.

### Overriding

`--include` pulls in anything these rules skip:

```bash
repo2readme run --local . --include "data/schema.json"
```

## File encodings

Files are read as bytes and decoded through a fixed chain, in this order:

| Step | Encoding | Why |
| --- | --- | --- |
| 1 | the encoding declared by a byte order mark | UTF-8, UTF-16 and UTF-32 BOMs are an explicit statement of encoding |
| 2 | `utf-8-sig` | UTF-8, with a BOM consumed rather than kept as the first character |
| 3 | `cp1252` | what Windows editors wrote before UTF-8 became the default |
| 4 | `latin-1` | accepts any byte sequence, so the chain always terminates |

The encoding that was used is reported at debug level:

```bash
repo2readme run --local . -vv
```

Before a file is read it is checked for binary content. A file is treated as
binary when it starts with a known binary signature (PNG, ZIP, ELF, ...), when
it contains a null byte outside a BOM-declared encoding, or when the decoded
sample is mostly control characters. Everything else is treated as text.

One case is deliberately not recoverable: **UTF-16 without a byte order mark**.
Those files are half null bytes and carry nothing to distinguish them from
binary data, so they are skipped as `binary_file`. Re-saving them with a BOM,
or as UTF-8, makes them readable. Use `--include` if you need a file the binary
check refuses.

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

## Language detection

The language of a file is decided once, during traversal, and then travels with
the document. Detection tries, in order:

1. the file extension (`.py`, `.ts`, `.go`, ...)
2. the filename, for files that have no extension (`Dockerfile`, `Makefile`,
   `Jenkinsfile`, `Gemfile`, `Rakefile`, ...)
3. a `#!` shebang on the first line
4. content markers

The result is stored on the document as `metadata["language"]` and is what the
summarizer is told and what the cache key is built from, so a `Gemfile` is
summarized as Ruby and a `Jenkinsfile` as Groovy rather than as whatever their
punctuation resembles.

Run with `-vv` to see the language chosen per file.

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

These are the *resolved* values, not the flags as typed. `--provider groq`,
`--provider GROQ` and no flags at all are the same run, so they share a cache;
hashing the raw flags meant they invalidated each other's entries. Aliases
(`--provider gemini` and `--provider google`) collapse to the same key too.
`--reviewer-*` does not affect the cache, since nothing the reviewer does is
cached.

When invalidation occurs, all existing cache entries are discarded and summaries are regenerated on the next run.

### When the cache is written

Rewriting the cache means rewriting the whole file, so writing once per
summarized file made a run cost one full serialization per file. The CLI
therefore batches: entries accumulate in memory and are written once, at the
end of the run, including when the run is interrupted part way through.

Used as a library, `SummaryCache` keeps writing on every `put()` by default.
Pass `autosave=False` and call `flush()` yourself (or use it as a context
manager) to batch, or `autosave_every=N` to write every N updates:

```python
from repo2readme.cache import SummaryCache

with SummaryCache(cache_dir, config, prompt_hash, autosave=False) as cache:
    for path, content, language in files:
        cache.put(path, content, language, summarize(path), mtime)
# flushed once on exit
```

`cache.stats()` reports hits, misses, in-memory updates, removals,
invalidations and how many times the file was actually rewritten.

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
