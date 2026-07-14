import os
import json
from rich import print as rprint
try:
    import click
except Exception:
    click = None

ENV_PATH = os.path.join(os.path.expanduser("~"), ".repo2readme_env.json")


def load_env():
    if not os.path.exists(ENV_PATH):
        return {}
    with open(ENV_PATH, "r") as f:
        return json.load(f)


def save_env(data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(ENV_PATH, flags, 0o600)
    if hasattr(os, 'fchmod'):
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=4)

def get_api_keys():
    env = load_env()

    groq = env.get("GROQ_API_KEY")
    gemini = env.get("GOOGLE_API_KEY")

    if not groq:
        groq = get_api_key("groq")

    if not gemini:
        gemini = get_api_key("google")

    return groq, gemini

def get_api_key(provider: str):
    env = load_env()

    provider_map = {
        "groq": "GROQ_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "together": "TOGETHER_API_KEY",
    }

    provider = provider.lower()

    if provider not in provider_map:
        raise ValueError(f"Unsupported provider: {provider}")

    env_var = provider_map[provider]
    api_key = env.get(env_var)

    if api_key:
        return api_key

    rprint(f"[yellow]{provider} API key is missing![/yellow]\n")

    # Use Click prompt when available so CLI prompting integrates with Click
    # and is testable via click.testing.CliRunner. Fall back to built-in
    # input() if Click isn't present.
    if click is not None:
        prompt_text = f"Enter your {provider} API key"
        try:
            api_key = click.prompt(prompt_text, hide_input=True, default="", show_default=False).strip()
        except Exception:
            api_key = input(f"Enter your {provider} API key: ").strip()
    else:
        api_key = input(f"Enter your {provider} API key: ").strip()

    env[env_var] = api_key
    save_env(env)

    rprint("[green]API key saved successfully![/green]")

    return api_key


def reset_api_keys():
    if os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)
        return True
    return False
