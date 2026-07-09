import os
import json
from rich import print as rprint

ENV_PATH = os.path.join(os.path.expanduser("~"), ".repo2readme_env.json")


def load_env():
    if not os.path.exists(ENV_PATH):
        return {}
    with open(ENV_PATH, "r") as f:
        return json.load(f)


def save_env(data):
    with open(ENV_PATH, "w") as f:
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
