import click
from rich import print as rprint
from rich.progress import Progress

from repo2readme.loaders.repo_loader import RepoLoader

from repo2readme.utils.detect_language import detect_lang
from repo2readme.summerize.summary_chain import summarize_file
from repo2readme.utils.tree import extract_tree
from repo2readme.readme.readme_generator import generate_readme


@click.command()
@click.option("--url", "-u", prompt=False, help="Url of github repository")
@click.option("--local", "-l", prompt=False, help="Path of the local repository")
@click.option("--output", "-o", default=None, required=False,
              help="Use -o to save generated readme to default README.md, or -o filename.md")
def main(url, local, output):

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

    summaries = []
    with Progress() as progress:
        task_sum = progress.add_task("[green]Summarizing files...", total=len(files))

        for file in files:
            language = detect_lang(file.metadata["file_type"])
            summary = summarize_file(
                file_path=file.metadata["file_path"],
                language=language,
                content=file.page_content
            )
            summaries.append(summary)
            progress.update(task_sum, advance=1)

    with Progress() as progress:
        task_readme = progress.add_task("[magenta]Generating README...", total=2)

        # Step 1: Build tree
        tree, file_paths = extract_tree(root_path)
        progress.update(task_readme, advance=1)

        # Step 2: Build README content
        readme = generate_readme(
            summaries=summaries,
            tree_structure=tree,
            file_paths=file_paths
        )
        progress.update(task_readme, advance=1)

        # Step 3: Save or print
        if output is None:
            rprint("[green]Printing README...\n[/green]")
            rprint(readme)
        else:
            save_path = output if output != "" else "README.md"
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(readme)
                rprint(f"[green]README saved to:[/green] {save_path}")
            except Exception as e:
                rprint(f"[red]Failed to save README: {e}[/red]")


    # Cleanup temp repo
    if cleanup_later:
        loader.cleanup()


if __name__ == "__main__":
    main()
