import click
from loaders.repo_loader import RepoLoader
from utils.detect_language import detect_lang
from summerize.summary_chain import summarize_file
from readme.readme_generator import generate_readme
@click.command()
@click.option("--url","-u",help="Url of the github repo")
def main(url):
    source=url
    files = RepoLoader(source).load()
    summaries=[]
    for file in files:
        file_language=detect_lang(file.metadata["file_type"])
        summaries.append(summarize_file(file.metadata["file_path"],file_language,file.page_content))
    print(generate_readme(summaries))
    

if __name__ == "__main__":
    main()