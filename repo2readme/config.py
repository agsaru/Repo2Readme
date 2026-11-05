import os
import json
from rich import print as rprint

from repo2readme.providers import get_provider

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
    """Return the stored API key for a provider, prompting for it if missing.

    Providers that do not authenticate (for example a local Ollama server)
    return ``None`` instead of prompting.
    """
    spec = get_provider(provider)

    if not spec.requires_api_key:
        return None

    env_var = spec.env_var
    api_key = os.environ.get(env_var)
    if api_key:
        return api_key

    env = load_env()
    api_key = env.get(env_var)

    if api_key:
        return api_key

    rprint(f"[yellow]{spec.label} API key is missing![/yellow]\n")

    # Use Click prompt when available so CLI prompting integrates with Click
    # and is testable via click.testing.CliRunner. Fall back to built-in
    # input() if Click isn't present.
    if click is not None:
        prompt_text = f"Enter your {spec.label} API key"
        # Let click.Abort (Ctrl-C, EOF) propagate: catching it here would
        # prompt a second time or surface a bare EOFError.
        api_key = click.prompt(
            prompt_text, hide_input=True, default="", show_default=False
        ).strip()
    else:
        api_key = input(f"Enter your {spec.label} API key: ").strip()

    if not api_key or len(api_key) < 8:
        raise ValueError(f"Invalid {spec.label} API key. Key must be at least 8 characters.")

    env[env_var] = api_key
    save_env(env)

    rprint("[green]API key saved successfully![/green]")

    return api_key


def reset_api_keys():
    if os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)
        return True
    return False
