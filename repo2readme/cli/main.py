import click
from rich import print as rprint
from rich.progress import Progress

# Adjust these imports if necessary to match your folder structure
from repo2readme.loaders.repo_loader import RepoLoader
from repo2readme.utils.detect_language import detect_lang
from repo2readme.summerize.summary_chain import summarize_file
from repo2readme.utils.tree import extract_tree
from repo2readme.readme.readme_generator import generate_readme

@click.command()
@click.option("--url", "-u", prompt=False, help="Url of github repository")
@click.option("--local", "-l", prompt=False, help="Path of the local repository")
@click.option(
    "--output", "-o",
    required=False,      
    flag_value="README.md",  # <--- KEY FIX: Use this string if -o is typed alone
    default=None,            # <--- KEY FIX: Use None if -o is omitted
    help="Save generated readme."
)
def main(url, local, output):

    # --- DEBUG PRINT (Remove later) ---
    # This proves you are running the correct file
    rprint("[yellow]Debug: Running the UPDATED cli/main.py[/yellow]") 
    
    # 1. Handle Inputs
    if not url and not local:
        choice = click.prompt(
            "No repository source provided. Load from (1) Github or (2) Local Folder",
            type=click.Choice(['1', '2']),
            show_choices=True
        )
        if choice == '1':
            url = click.prompt("Enter GitHub repository URL")
        else:
            local = click.prompt("Enter local repository path")

    if url and local:
        rprint("[red]Error: Provide only one of --url or --local[/red]")
        return

    source = url if url else local
    cleanup_later = True if url else False

    # 2. Load Repo
    files = []
    root_path = ""
    loader = None

    with Progress() as progress:
        task_load = progress.add_task("[cyan]Loading repository...", total=1)
        try:
            loader_obj = RepoLoader(source)
            files, root_path, loader = loader_obj.load()
            progress.update(task_load, advance=1)
        except Exception as e:
            progress.update(task_load, advance=1)
            rprint(f"[red]Failed to load repository: {e}[/red]")
            return

    # 3. Summarize
    summaries = []
    with Progress() as progress:
        task_sum = progress.add_task("[green]Summarizing files...", total=len(files))
        for file in files:
            try:
                language = detect_lang(file.metadata.get("file_type", "text"))
                summary = summarize_file(
                    file_path=file.metadata["file_path"],
                    language=language,
                    content=file.page_content
                )
                summaries.append(summary)
            except Exception as e:
                pass
            progress.update(task_sum, advance=1)

    # 4. Generate Readme
    readme = ""
    with Progress() as progress:
        task_readme = progress.add_task("[magenta]Generating README...", total=2)
        tree, file_paths = extract_tree(root_path)
        progress.update(task_readme, advance=1)
        
        readme = generate_readme(
            summaries=summaries,
            tree_structure=tree,
            file_paths=file_paths
        )
        progress.update(task_readme, advance=1)

    # 5. Output Logic (The Fix)
    if output is None:
        rprint("\n[green]Printing README to console...[/green]\n")
        rprint(readme)
    else:
        save_path = output
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(readme)
            rprint(f"[green]✔ README saved to:[/green] [bold]{save_path}[/bold]")
        except Exception as e:
            rprint(f"[red]Failed to save README: {e}[/red]")

    if cleanup_later and loader:
        loader.cleanup()

if __name__ == "__main__":
    main()