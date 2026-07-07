import os
import json
from rich import print as rprint

ENV_PATH = os.path.join(os.path.expanduser("~"), ".repo2readme_env.json")


# -------------------------------------------------------
# Supported API Keys
# Extend this dictionary when adding new providers.
# -------------------------------------------------------

SUPPORTED_API_KEYS = {
    "groq": ("GROQ_API_KEY", "Groq"),
    "google": ("GOOGLE_API_KEY", "Google Gemini"),
    "gemini": ("GOOGLE_API_KEY", "Google Gemini"),
}


def load_env():
    if not os.path.exists(ENV_PATH):
        return {}

    with open(ENV_PATH, "r") as f:
        return json.load(f)


def save_env(data):
    with open(ENV_PATH, "w") as f:
        json.dump(data, f, indent=4)


def get_api_keys(provider=None):
    """
    Loads API keys required for the selected provider.

    If no provider is specified, all supported providers
    are checked to preserve backward compatibility.

    Returns
    -------
    dict
    """

    env = load_env()

    if provider:
        provider = provider.lower()

        if provider not in SUPPORTED_API_KEYS:
            raise ValueError(f"Unsupported provider: {provider}")

        required_keys = [SUPPORTED_API_KEYS[provider]]
    else:
        # Backward compatibility
        required_keys = list(dict.fromkeys(SUPPORTED_API_KEYS.values()))

    missing = []

    for key, provider_name in required_keys:
        if not env.get(key):
            missing.append((key, provider_name))

    if missing:
        rprint("[yellow]Some API keys are missing.[/yellow]\n")

        for key, provider_name in missing:
            while True:
                value = input(
                    f"Enter your {provider_name} API key: "
                ).strip()

                if value:
                    env[key] = value
                    break

                rprint("[red]API key cannot be empty.[/red]")

        save_env(env)

        rprint("[green]API keys saved successfully![/green]")

    return {
        key: env.get(key)
        for key, _ in dict.fromkeys(SUPPORTED_API_KEYS.values())
    }


def reset_api_keys():
    if os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)
        return True

    return False