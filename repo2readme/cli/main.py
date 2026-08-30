from dotenv import load_dotenv
load_dotenv()

import click
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.progress import Progress
from rich.table import Table
from repo2readme.config import reset_api_keys
import os
from collections import Counter

from repo2readme import __version__
from repo2readme.utils.logging_config import logging_options
from repo2readme.utils.output import (
    OutputPathError,
    backup_path_for,
    prepare_output_path,
    write_readme,
)
from repo2readme.utils.tree import generate_tree_from_paths
from repo2readme.cache import SummaryCache
from repo2readme.loaders.repo_loader import RepoLoader
from repo2readme.summarize.summary import get_prompt_template_hash
from repo2readme.dependency_graph import build_dependency_graph
from repo2readme.llm.settings import (
    UnknownProviderError,
    resolve_reviewer_settings,
    resolve_settings,
)
from repo2readme.providers import PROVIDERS, provider_choices_help

# Import new services
from repo2readme.services.environment import setup_api_keys
from repo2readme.services.estimation import format_size, estimate_analysis_cost
from repo2readme.services.summarization import generate_all_summaries, generate_hierarchical_summaries
from repo2readme.services.orchestrator import ReadmeGenerationError, run_pipeline
from repo2readme.services.reporting import partition_summaries, render_report
from repo2readme.utils.workers import validate_max_workers


def validate_max_workers_option(ctx, param, value):
    """Reject an unusable --max-workers before the repository is loaded.

    Without this the value travelled all the way to ThreadPoolExecutor, which
    raised part way through the summarization progress bar - after the clone,
    the traversal and the user's confirmation of the token estimate.
    """
    try:
        return validate_max_workers(value)
    except ValueError as e:
        raise click.BadParameter(str(e), ctx=ctx, param=param) from e


@click.group()
@click.version_option(version=__version__, prog_name="repo2readme")
def main():
    """
    Use the `run` command to generate a README.
    Use the `reset` command to clear saved API keys.

    Note: First run will ask for your API keys.
    """


@main.command()
@logging_options
@click.option(
    "--url",
    "-u",
    help="Git repository URL (https, ssh, git:// or git@host:path).",
)
@click.option("--local", "-l", help="Local repo path")
@click.option("--output", "-o", default=None, type=click.Path(), help="Save README to file")
@click.option("--force", "-f", is_flag=True, help="Overwrite output file without confirmation")
@click.option(
    "--backup",
    is_flag=True,
    default=False,
    help="Keep a copy of the file being replaced, alongside it with a .bak suffix.",
)
@click.option(
    "--create-dirs/--no-create-dirs",
    default=True,
    show_default=True,
    help="Create the output file's parent directory when it does not exist.",
)
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
    "--strict",
    is_flag=True,
    default=False,
    help="Exit with a non-zero status if any file fails to summarize.",
)
@click.option(
    "--respect-gitignore",
    is_flag=True,
    default=False,
    help="Respect .gitignore and .git/info/exclude patterns during repository traversal",
)
@click.option(
    "--max-workers",
    default=None,
    type=int,
    callback=validate_max_workers_option,
    help="Number of parallel worker threads for file processing (default: 4, capped at file count)",
)
@click.option(
    "--provider",
    default=None,
    help=f"LLM provider ({provider_choices_help()}). Run 'repo2readme providers' for details.",
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
@click.option(
    "--reviewer-provider",
    default=None,
    help=(
        "LLM provider for the README review step. Defaults to --provider. "
        "Only set this to review with a different vendor on purpose."
    ),
)
@click.option(
    "--reviewer-model",
    default=None,
    help="Model for the README review step. Defaults to --model.",
)
@click.option(
    "--reviewer-base-url",
    default=None,
    help="Base URL for the README review step. Defaults to --base-url.",
)
@click.option(
    "--branch",
    "-b",
    default="main",
    show_default=True,
    help="Branch to clone when using --url.",
)
def run(url, local, output, force, backup, create_dirs, include_patterns, exclude_patterns, max_file_size_kb, dry_run, strict, respect_gitignore, max_workers, provider, model, base_url, reviewer_provider, reviewer_model, reviewer_base_url, branch):
    """ Use --url for GitHub repo url and --local for local repo
    """
    if not url and not local:
        rprint("[red]Provide either --url or --local[/red]")
        return

    source = url if url else local

    # Check the destination before anything is loaded or summarized. This used
    # to happen in the open() at the very end of the run, so a missing parent
    # directory threw away every API call the run had already paid for.
    output_target = None
    if output is not None:
        try:
            output_target = prepare_output_path(output, create_parents=create_dirs)
        except OutputPathError as e:
            rprint(f"[red]{escape(str(e))}[/red]")
            raise SystemExit(2) from e

        if output_target.created_parent:
            rprint(f"[green]Created {output_target.path.parent}[/green]")

    # Resolve the provider, model and base URL once, before anything expensive
    # happens. A typo in --provider used to survive the clone, the traversal
    # and the API key prompt and only then raise.
    try:
        settings = resolve_settings(provider, model, base_url)
        reviewer_settings = resolve_reviewer_settings(
            settings, reviewer_provider, reviewer_model, reviewer_base_url
        )
    except UnknownProviderError as e:
        rprint(f"[red]{e}[/red]")
        raise SystemExit(2) from e

    # Initialize file summary cache
    cache_dir = os.path.join(os.getcwd(), ".repo2readme", "cache")
    # Keyed on the resolved settings rather than on the raw flags, so
    # `--provider groq` and no flags at all - the same run - share a cache
    # instead of invalidating each other.
    summarization_config = settings.as_cache_config()
    # autosave=False batches the writes: the whole cache file has to be
    # rewritten for any change, so saving once per summarized file made a run
    # cost one full serialization per file. The run flushes once at the end,
    # in the finally block, so an interrupted run still keeps its work.
    summary_cache = SummaryCache(
        cache_dir=cache_dir,
        config=summarization_config,
        prompt_template_hash=get_prompt_template_hash(),
        autosave=False,
    )

    with Progress() as progress:
        task = progress.add_task("[cyan]Loading repository...", total=1)
        try:
            loader = RepoLoader(
                source,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                max_file_size_kb=max_file_size_kb,
                respect_gitignore=respect_gitignore,
                max_workers=max_workers,
                branch=branch,
            )
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
    
    # Build dependency graph for README enrichment
    dependency_graph = build_dependency_graph(documents)
    dependency_overview = dependency_graph.to_markdown_summary()

    # Build the tree from the documents that were actually loaded, so the
    # "Folder Structure" section of the README cannot advertise files that were
    # filtered out of the analysis.
    tree = generate_tree_from_paths(
        root_path,
        [doc["metadata"].get("relative_path", "") for doc in documents],
    )

    estimated_tokens, total_size_bytes, total_documents = estimate_analysis_cost(documents)

    if dry_run:
        rprint("\n[bold]Repository Tree[/bold]\n")
        rprint(tree)
        rprint("\n[bold]Files to be processed[/bold]\n")
        for doc in documents:
            rel_path = doc["metadata"].get("relative_path", "")
            rprint(f"✓ [green]{rel_path}[/green]")
        if skipped:
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
        rprint(f"Model              : {settings.describe()}")
        if reviewer_settings != settings:
            rprint(f"Reviewer           : {reviewer_settings.describe()}")
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
    rprint(f"Model              : {settings.describe()}")
    if reviewer_settings != settings:
        rprint(f"Reviewer           : {reviewer_settings.describe()}")

    try:
        if not force:
            proceed = click.confirm("\nProceed?", default=False)
            if not proceed:
                rprint("[yellow]Operation cancelled.[/yellow]")
                return

        try:
            # Only the providers this run will actually call, deduplicated:
            # both keys used to be demanded whenever --provider was omitted.
            setup_api_keys(settings, reviewer_settings)
        except Exception as e:
            rprint(f"[red]Failed to configure API keys: {e}[/red]")
            return

        with Progress() as progress:
            task = progress.add_task("[cyan]Generating summaries...[/cyan]", total=total_documents)
            summaries, errors = generate_all_summaries(
                documents=documents,
                summary_cache=summary_cache,
                provider=settings.provider,
                model=settings.model,
                base_url=settings.base_url,
                max_workers=max_workers,
                progress=progress,
                task_id=task
            )

        # Failure placeholders must not reach the roll-up or the README prompt,
        # so split them out before anything else consumes them.
        successful_summaries, failures = partition_summaries(summaries)
        failures.extend(errors)
        render_report(total_documents, len(successful_summaries), failures, rprint)

        if total_documents and not successful_summaries:
            rprint(
                "\n[red]Every file failed to summarize, so there is nothing to "
                "generate a README from.[/red]"
            )
            raise SystemExit(1)

        with Progress() as progress:
            rollup_task = progress.add_task("[cyan]Generating directory summaries...[/cyan]", total=1)
            hierarchical_summaries = generate_hierarchical_summaries(
                file_summaries=successful_summaries,
                provider=settings.provider,
                model=settings.model,
                base_url=settings.base_url,
                progress=progress,
                task_id=rollup_task
            )

        # Remove cache entries for files that no longer exist
        current_files = {doc["metadata"]["file_path"] for doc in documents}
        stale_entries = summary_cache.get_deleted_files(current_files)
        if stale_entries:
            stale_paths = [e["file_path"] for e in stale_entries]
            summary_cache.remove_entries(stale_paths)

        rprint("[cyan]Generating README...[/cyan]")
        
        try:
            readme = run_pipeline(
                summaries=hierarchical_summaries,
                tree=tree,
                dependency_overview=dependency_overview,
                settings=settings,
                reviewer_settings=reviewer_settings,
            )
        except ReadmeGenerationError as e:
            # Nothing is written: an empty README would replace the user's
            # existing file with zero bytes.
            rprint(f"\n[red]{e}[/red]")
            rprint(
                "[yellow]Nothing was written. Re-run to try again, or use "
                "-v to see the reviewer's diagnostics.[/yellow]"
            )
            raise SystemExit(1) from e

        if output_target is None:
            rprint("\n[green]Generated README:[/green]\n")
            rprint(readme)
        else:
            destination = output_target.path
            replacing = destination.exists()

            if replacing and not force:
                should_overwrite = click.confirm(
                    f"{destination} already exists. Do you want to overwrite it?",
                    default=False,
                )

                if not should_overwrite:
                    rprint("[yellow]Output file was not overwritten.[/yellow]")
                    return

            try:
                write_readme(destination, readme, backup=backup)
            except OSError as e:
                # The README exists and was paid for; printing it is the only
                # way the user keeps it. Silently discarding it is not.
                rprint(f"\n[red]Could not write {destination}: {escape(str(e))}[/red]")
                rprint("[yellow]Printing the README instead.[/yellow]\n")
                rprint(readme)
                raise SystemExit(1) from e

            rprint(f"[green]Saved to {destination}[/green]")
            if backup and replacing:
                rprint(f"[green]Previous version kept at {backup_path_for(destination)}[/green]")

        if strict and failures:
            rprint(
                f"[red]--strict: {len(failures)} file(s) failed to summarize.[/red]"
            )
            raise SystemExit(1)

    finally:
        # One write for the whole run, including when the run was interrupted
        # part way through.
        summary_cache.flush()
        if hasattr(loader_obj, "cleanup"):
            loader_obj.cleanup()


@main.command()
def providers():
    """List the supported LLM providers and their defaults."""
    table = Table(title="Supported providers", header_style="bold cyan")
    table.add_column("Provider")
    table.add_column("Aliases")
    table.add_column("Default model")
    table.add_column("API key env var")

    for spec in PROVIDERS:
        table.add_row(
            spec.name,
            ", ".join(spec.aliases) or "-",
            spec.default_model,
            spec.env_var or "not required",
        )

    console = Console()
    console.print(table)
    rprint(
        "\nUse with: [cyan]repo2readme run --local . --provider <name> "
        "[--model <model>][/cyan]"
    )


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