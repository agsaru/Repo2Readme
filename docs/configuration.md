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
