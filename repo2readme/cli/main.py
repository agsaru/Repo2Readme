import click
from rich import print as rprint
from rich.progress import Progress
from repo2readme.config import (
    get_api_keys,
    get_api_key,
    reset_api_keys,
)
import os
from repo2readme.utils.tree import generate_tree
from repo2readme.utils.detect_language import detect_lang
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


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
@click.option(
    "--provider",
    default=None,
    help="LLM provider (groq, google, openai, anthropic, openrouter, ollama, etc.)",
)
@click.option(
    "--model",
    default=None,
    help="LLM model name",
)
@click.option(
    "--base-url",
    default=None,
    help="Base URL for OpenAI-compatible providers",
)
def run(url, local, output, force, include_patterns, exclude_patterns, max_file_size_kb, dry_run, provider, model, base_url,):
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
            loader = RepoLoader(source, include_patterns=include_patterns, exclude_patterns=exclude_patterns, max_file_size_kb=max_file_size_kb)
            if dry_run:
                files, root_path, loader_obj, skipped = loader.load(return_skip_info=True)
            else:
                files, root_path, loader_obj = loader.load()
                skipped = []
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
    tree = generate_tree(root_path)

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
        rprint("\n[bold]Repository Tree[/bold]\n")
        rprint(tree)
        rprint("\n[bold]Files to be processed[/bold]\n")
        for doc in documents:
            rel_path = doc["metadata"].get("relative_path", "")
            rprint(f"✓ [green]{rel_path}[/green]")
        if skipped:
            from collections import Counter
            skip_reasons = Counter()
            for _, reason in skipped:
                skip_reasons[reason] += 1
            rprint("\n[bold]Skipped Files Summary[/bold]\n")
            reason_order = ["excluded by pattern", "ignored by default rules", "exceeds maximum file size", "protected large file"]
            printed = set()
            for reason in reason_order:
                if reason in skip_reasons:
                    printed.add(reason)
                    rprint(f"{reason:30s}: {skip_reasons[reason]}")
            for reason in sorted(skip_reasons):
                if reason not in printed:
                    rprint(f"{reason:30s}: {skip_reasons[reason]}")
        rprint("\n[bold]Repository Analysis[/bold]\n")
        rprint(f"Files selected     : {total_documents}")
        rprint(f"Estimated tokens   : ~{estimated_tokens:,}")
        rprint(f"Request size       : ~{format_size(total_size_bytes)}")
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

    try:
        if not force:
            proceed = click.confirm("\nProceed?", default=False)
            if not proceed:
                rprint("[yellow]Operation cancelled.[/yellow]")
                return

        try:
            if provider:
                api_key = get_api_key(provider)

                provider_env = {
                    "groq": "GROQ_API_KEY",
                    "google": "GOOGLE_API_KEY",
                    "gemini": "GOOGLE_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openrouter": "OPENROUTER_API_KEY",
                    "together": "TOGETHER_API_KEY",
            }

                os.environ[provider_env[provider.lower()]] = api_key

            else:
                groq_key, gemini_key = get_api_keys()
                os.environ["GROQ_API_KEY"] = groq_key
                os.environ["GOOGLE_API_KEY"] = gemini_key

        except Exception as e:
            rprint(f"[red]Failed to configure API keys: {e}[/red]")
            return

        from repo2readme.summarize.summary import summarize_file
        from repo2readme.readme.agent_workflow import workflow

        summaries = []
        errors = []
        
        # Skip summarization if there are no documents
        if total_documents > 0:
            summaries_lock = threading.Lock()
            errors_lock = threading.Lock()
            
            def process_document(doc):
                meta = doc["metadata"]
                try:
                    lang = detect_lang(meta.get("file_type", "text"))
                    if provider or model or base_url:
                        summary = summarize_file(
                            file_path=meta["file_path"],
                            language=lang,
                            content=doc["content"],
                            provider=provider,
                            model_name=model,
                            base_url=base_url,
    )
                    else:
                        summary = summarize_file(
                            file_path=meta["file_path"],
                            language=lang,
                            content=doc["content"],
    )
                    with summaries_lock:
                        summaries.append(summary)
                except Exception as e:
                    with errors_lock:
                        errors.append(f"Error processing {meta.get('file_path')}: {e}")
            
            with Progress() as progress:
                task = progress.add_task("[cyan]Generating summaries...[/cyan]", total=total_documents)
                
                # Limit concurrent workers to avoid overwhelming API providers
                max_workers = min(2, total_documents)
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(process_document, doc): doc for doc in documents}
                    
                    for future in as_completed(futures):
                        progress.update(task, advance=1)

        rprint("[cyan]Generating README...[/cyan]")

        initial_state = {
            "summaries": summaries,
            "tree_structure": tree,
            "iteration_no": 0,
            "max_iterations": 3,
            "latest_readme": "",
            'best_score': 0.0,
            "best_readme": "",
            "provider": provider,
            "model": model,
            "base_url": base_url,
        }

        final_state = workflow.invoke(initial_state)
        readme = final_state['best_readme']

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

    finally:
        if hasattr(loader_obj, "cleanup"):
            loader_obj.cleanup()


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
