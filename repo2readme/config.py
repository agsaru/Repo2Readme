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

    if groq and gemini:
        return groq, gemini

    rprint("[yellow]API keys are missing! Let's add them.[/yellow]\n")

    if not groq:
        groq = input("Enter your Groq API key: ").strip()
    if not gemini:
        gemini = input("Enter your Google Gemini API key: ").strip()

    env["GROQ_API_KEY"] = groq
    env["GOOGLE_API_KEY"] = gemini

    save_env(env)

    rprint("[green]API keys saved successfully![/green]")

    return groq, gemini


def reset_api_keys():
    if os.path.exists(ENV_PATH):
        os.remove(ENV_PATH)
        return True
    return False
