import os
import json
from rich import print as rprint

ENV_PATH = os.path.join(os.path.expanduser("~"), ".repo2readme_env.json")


# -------------------------------------------------------
# Supported API Keys
# Extend this dictionary when adding new providers.
# -------------------------------------------------------

SUPPORTED_API_KEYS = {
    "GROQ_API_KEY": "Groq",
    "GOOGLE_API_KEY": "Google Gemini",
}


def load_env():
    if not os.path.exists(ENV_PATH):
        return {}

    with open(ENV_PATH, "r") as f:
        return json.load(f)


def save_env(data):
    with open(ENV_PATH, "w") as f:
        json.dump(data, f, indent=4)


def get_api_keys():
    """
    Loads all configured API keys.

    If any required API key is missing,
    the user is prompted only for the missing key.

    Returns
    -------
    dict

    Example:

    {
        "GROQ_API_KEY": "...",
        "GOOGLE_API_KEY": "..."
    }
    """

    env = load_env()

    missing = [
        key
        for key in SUPPORTED_API_KEYS
        if not env.get(key)
    ]

    if missing:
        rprint("[yellow]Some API keys are missing.[/yellow]\n")

        for key in missing:
            provider_name = SUPPORTED_API_KEYS[key]
            env[key] = input(
                f"Enter your {provider_name} API key: "
            ).strip()

        save_env(env)

        rprint("[green]API keys saved successfully![/green]")

    return {
        key: env.get(key)
        for key in SUPPORTED_API_KEYS
    }


def reset_api_keys():
    if os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)
        return True

    return False