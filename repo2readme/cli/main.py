import click
from rich import print as rprint
from rich.progress import Progress
from repo2readme.config import get_api_keys,reset_api_keys
import os
from repo2readme.utils.tree import generate_tree
from repo2readme.utils.detect_language import detect_lang

@click.group()
def main():
   """
    Use the `run` command to generate a README.
    Use the `reset` command to clear saved API keys.

    Note: First run will ask for your API keys.
    """

@main.command()
@click.option("--url", "-u", help="GitHub repo URL")
@click.option("--local", "-l", help="Local repo path")
@click.option("--output", "-o", default=None, type=click.Path(), help="Save README to file")
@click.option("--force", "-f", is_flag=True, help="Overwrite output file without confirmation")
@click.option(
    "--include",
    "include_patterns",
    multiple=True,
    help="Glob pattern for files to include even if ignored by default. Can be used multiple times.",
)
@click.option(
    "--exclude",
    "exclude_patterns",
    multiple=True,
    help="Glob pattern for files to exclude. Can be used multiple times.",
)
@click.option(
    "--max-file-size-kb",
    default=200,
    show_default=True,
    type=int,
    help="Maximum file size in KB to include during repository analysis.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview the analysis without making any API calls.",
)
def run(url, local, output, force, include_patterns, exclude_patterns, max_file_size_kb, dry_run):
    """ Use --url for GitHub repo url and --local for local repo
    """
    if not url and not local:
        rprint("[red]Provide either --url or --local[/red]")
        return

    source = url if url else local
    
    from repo2readme.loaders.repo_loader import RepoLoader

    with Progress() as progress:
        task = progress.add_task("[cyan]Loading repository...", total=1)
        try:
            loader = RepoLoader(source,include_patterns=include_patterns,exclude_patterns=exclude_patterns,max_file_size_kb=max_file_size_kb,)
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
    tree= generate_tree(root_path)

    # Estimate token count (roughly 3 characters per token)
    estimated_tokens = sum(max(1, len(doc["content"]) // 3) for doc in documents)
    total_size_bytes = sum(len(doc["content"].encode("utf-8")) for doc in documents)
    total_documents = len(documents)

    def format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    if dry_run:
        rprint("\n[bold]Repository Analysis[/bold]\n")
        rprint(f"Files selected     : {total_documents}")
        rprint(f"Estimated tokens   : ~{estimated_tokens:,}")
        rprint(f"Request size       : ~{format_size(total_size_bytes)}")
        rprint("\n[bold]Repository Tree[/bold]\n")
        rprint(tree)
        rprint("\n[bold]Files to be processed[/bold]\n")
        for doc in documents:
            rel_path = doc["metadata"].get("relative_path", "")
            rprint(f"✓ [green]{rel_path}[/green]")
        rprint("\n[green]Dry run complete.[/green]")
        rprint("[yellow]No API requests were made.[/yellow]")
        if hasattr(loader_obj, "cleanup"):
            loader_obj.cleanup()
        return

    # Normal execution: print estimation first
    rprint("\n[bold]Repository Analysis[/bold]\n")
    rprint(f"Files to summarize : {total_documents}")
    rprint(f"Estimated tokens   : ~{estimated_tokens:,}")
    rprint(f"Request size       : ~{format_size(total_size_bytes)}")

    if not force:
        proceed = click.confirm("\nProceed?", default=False)
        if not proceed:
            rprint("[yellow]Operation cancelled.[/yellow]")
            if hasattr(loader_obj, "cleanup"):
                loader_obj.cleanup()
            return

    # Now get API keys and setup environment since we are proceeding to make API calls
    try:
        groq_key, gemini_key = get_api_keys()
        os.environ["GROQ_API_KEY"] = groq_key
        os.environ["GOOGLE_API_KEY"] = gemini_key
    except Exception as e:
        rprint(f"[red]Failed to configure API keys: {e}[/red]")
        if hasattr(loader_obj, "cleanup"):
            loader_obj.cleanup()
        return

    from repo2readme.summarize.summary import summarize_file
    from repo2readme.readme.agent_workflow import workflow

    summaries = []
    errors=[]
    with Progress() as progress:
        task=progress.add_task("[cyan]Generating summaries...[/cyan]",total= total_documents)
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
              
                errors.append(f"Error processing {meta.get('file_path')}: {e}")
            progress.update(task,advance=1)

    rprint("[cyan]Generating README...[/cyan]")

    initial_state={
        "summaries":summaries,
        "tree_structure":tree,
        "iteration_no":0,
        "max_iterations":3,
        "latest_readme":"",
        'best_score':0.0,
        "best_readme":""

    }

    final_state = workflow.invoke(initial_state)
    readme=final_state['best_readme']

    if hasattr(loader_obj, "cleanup"):
        loader_obj.cleanup()

    if output is None:
        rprint("\n[green]Generated README:[/green]\n")
        rprint(readme)
    else:
        if os.path.exists(output) and not force:
            should_overwrite = click.confirm(
                f"{output} already exists. Do you want to overwrite it?",
                default=False,
            )

            if not should_overwrite:
                rprint("[yellow]Output file was not overwritten.[/yellow]")
                return

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
