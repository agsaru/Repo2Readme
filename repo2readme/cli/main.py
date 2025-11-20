import click
from rich import print as rprint
from rich.progress import Progress


from repo2readme.config import get_api_keys,reset_api_keys
import os

from repo2readme.loaders.repo_loader import RepoLoader
from repo2readme.utils.tree import extract_tree

from repo2readme.summerize.summary import summarize_file
from repo2readme.readme.readme_generator import generate_readme
from repo2readme.utils.detect_language import detect_lang

@click.group()
def main():
    """readme cli"""

@main.command()
@click.option("--url", "-u", help="GitHub repo URL")
@click.option("--local", "-l", help="Local repo path")
@click.option("--output", "-o", default=None, help="Save README to file")
def run(url, local, output):
    groq_key, gemini_key = get_api_keys()
    os.environ["GROQ_API_KEY"] = groq_key
    os.environ["GOOGLE_API_KEY"] = gemini_key

    if not url and not local:
        rprint("[red]Provide either --url or --local[/red]")
        return

    source = url if url else local

    with Progress() as progress:
        task = progress.add_task("[cyan]Loading repository...", total=1)
        try:
            loader = RepoLoader(source)
            files, root_path, loader_obj = loader.load()
        except Exception as e:
            rprint(f"[red]Failed to load repository: {e}[/red]")
            return
        progress.update(task, advance=1)

    documents = []
    for f in files:
        documents.append({
            "content": f.page_content,
            "metadata": f.metadata
        })

    tree, file_paths = extract_tree(root_path)

    rprint("[cyan]Generating summaries...[/cyan]")

    summaries = []
    for doc in documents:
        meta = doc["metadata"]
        try:
            lang = detect_lang(meta.get("file_type", "text"))
            summary = summarize_file(
                file_path=meta["file_path"],
                language=lang,
                content=doc["content"]
            )
            summaries.append(summary)
        except Exception as e:
            summaries.append(f"Error processing {meta.get('file_path')}: {e}")

    rprint("[cyan]Generating README...[/cyan]")

    readme = generate_readme(
        summaries=summaries,
        tree_structure=tree,
        file_paths=file_paths
    )

    if output is None:
        rprint("\n[green]Generated README:[/green]\n")
        rprint(readme)
    else:
        with open(output, "w", encoding="utf-8") as f:
            f.write(readme)
        rprint(f"[green]Saved to {output}[/green]")


@main.command()
def reset():
    """Reset stored API keys"""

    if reset_api_keys():
        rprint("[green]API keys reset successfully![/green]")
        rprint("Run repo2readme again to reconfigure keys.")
    else:
        rprint("[yellow]No API key file found to reset.[/yellow]")


if __name__ == "__main__":
    main()

