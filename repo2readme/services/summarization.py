from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from repo2readme.utils.detect_language import detect_lang
from repo2readme.utils.workers import resolve_worker_count
from repo2readme.summarize.summary import summarize_file
from repo2readme.cache import SummaryCache
from repo2readme.services.reporting import SummaryFailure, is_failed_summary

def resolve_language(metadata: Dict[str, Any], content: str) -> str:
    """The language of a document, preferring what the traversal already found.

    The traversal pipeline detects the language from the full path *and* the
    content, so it can use every strategy ``detect_lang`` implements - the
    extension, the filename, a shebang, then content markers. That answer used
    to be dropped before it reached here, and this stage re-detected it from
    ``file_type``, which is the bare extension and empty for any file without
    one. A ``Gemfile`` came out as ``unknown`` and a ``Jenkinsfile`` as
    ``json``, and the wrong answer went into the summarizer prompt and the
    cache key.

    The fallback is kept for callers that build documents by hand, and is given
    the best path it can find rather than the extension alone.
    """
    language = metadata.get("language")
    if language and language != "unknown":
        return language

    path = (
        metadata.get("relative_path")
        or metadata.get("file_path")
        or metadata.get("file_name")
        or metadata.get("file_type")
        or "text"
    )
    return detect_lang(path, content)


def summary_cache_key(
    metadata: Dict[str, Any], cache_namespace: str | None = None
) -> str:
    """Stable cache key for a document, including a remote repository namespace."""
    file_path = metadata["file_path"]
    relative_path = metadata.get("relative_path")
    if cache_namespace and relative_path:
        relative_path = relative_path.replace("\\", "/")
        return f"{cache_namespace}/{relative_path}"
    return file_path


def generate_all_summaries(
    documents: List[Dict[str, Any]],
    summary_cache: SummaryCache,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    max_workers: int | None = None,
    progress=None,
    task_id=None,
    cache_namespace: str | None = None,
) -> tuple[List[Dict[str, Any]], List[SummaryFailure]]:
    """
    Concurrently generates summaries for all documents.

    Returns the summaries together with the files that raised before a summary
    could be produced. Summaries that came back as ``{"error": ...}``
    placeholders stay in the first list; use
    ``repo2readme.services.reporting.partition_summaries`` to split them out.
    """
    total_documents = len(documents)
    if total_documents == 0:
        return [], []

    summaries: list[Any | None] = [None] * total_documents
    errors: list[SummaryFailure | None] = [None] * total_documents

    def process_document(doc):
        meta = doc["metadata"]
        file_path = meta["file_path"]
        try:
            lang = resolve_language(meta, doc["content"])
            cache_key = summary_cache_key(meta, cache_namespace)
            cached = summary_cache.get(cache_key, doc["content"], lang)
            if cached is not None:
                summary = dict(cached) if isinstance(cached, dict) else cached
                if isinstance(summary, dict):
                    summary["file_path"] = file_path
                    if meta.get("relative_path"):
                        summary["relative_path"] = meta["relative_path"]
                return summary, None

            summary = summarize_file(
                file_path=file_path,
                language=lang,
                content=doc["content"],
                provider=provider,
                model_name=model,
                base_url=base_url,
            )
            if summary is None:
                raise ValueError("Summarizer returned no result")

            if isinstance(summary, dict) and "error" not in summary:
                summary = dict(summary)
                summary["file_path"] = file_path
                if meta.get("relative_path"):
                    summary["relative_path"] = meta["relative_path"]
                summary_cache.put(
                    cache_key, doc["content"], lang, summary, meta.get("mtime", 0)
                )

            return summary, None
        except Exception as exc:
            return None, SummaryFailure(file_path=file_path, reason=str(exc))

    effective_workers = resolve_worker_count(max_workers, total_documents)

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        futures = {
            executor.submit(process_document, doc): index
            for index, doc in enumerate(documents)
        }

        for future in as_completed(futures):
            index = futures[future]
            try:
                summaries[index], errors[index] = future.result()
            except Exception as exc:
                file_path = documents[index]["metadata"]["file_path"]
                errors[index] = SummaryFailure(file_path=file_path, reason=str(exc))

            if progress and task_id is not None:
                progress.update(task_id, advance=1)

    return (
        [summary for summary in summaries if summary is not None],
        [error for error in errors if error is not None],
    )


def build_directory_tree(file_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Builds a tree structure of the repository based on file paths.
    """
    tree = {"type": "dir", "path": ".", "files": [], "children": {}}
    for summary in file_summaries:
        if isinstance(summary, str):
            continue
        path = summary.get("relative_path") or summary.get("file_path", "")
        path = path.replace("\\", "/")
        if not path:
            continue
        parts = path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current["files"].append(summary)
            else:
                if part not in current["children"]:
                    current["children"][part] = {
                        "type": "dir",
                        "path": "/".join(parts[:i+1]),
                        "files": [],
                        "children": {}
                    }
                current = current["children"][part]
    return tree

def generate_hierarchical_summaries(
    file_summaries: List[Dict[str, Any]],
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    progress=None,
    task_id=None
) -> List[Dict[str, Any]]:
    """
    Rolls up file summaries into directory summaries recursively.
    """
    if len(file_summaries) <= 15:
        if progress and task_id is not None:
            progress.update(task_id, advance=1)
        return file_summaries
        
    tree = build_directory_tree(file_summaries)
    
    from repo2readme.summarize.directory_summary import summarize_directory
    
    def count_dirs(node):
        return 1 + sum(count_dirs(c) for c in node["children"].values())
        
    total_dirs = count_dirs(tree) - 1 # excluding root
    if progress and task_id is not None:
        progress.update(task_id, total=total_dirs, completed=0)
    
    def process_dir(node: Dict[str, Any]) -> Any:
        child_summaries = []
        for child_node in node["children"].values():
            child_summary = process_dir(child_node)
            if child_summary:
                if isinstance(child_summary, list):
                    child_summaries.extend(child_summary)
                else:
                    child_summaries.append(child_summary)
                
        contents = child_summaries + node["files"]
        if not contents:
            return None
            
        if node["path"] == ".":
            return contents

        if len(contents) == 1:
            if progress and task_id is not None:
                progress.update(task_id, advance=1)
            return contents[0]
            
        dir_summary = summarize_directory(
            dir_path=node["path"],
            contents_summaries=contents,
            provider=provider,
            model_name=model,
            base_url=base_url
        )
        
        if progress and task_id is not None:
            progress.update(task_id, advance=1)
            
        if not isinstance(dir_summary, dict) or is_failed_summary(dir_summary):
            return contents

        if not dir_summary.get("description"):
            return contents

        return dir_summary
        
    top_level_summaries = process_dir(tree)
    if isinstance(top_level_summaries, list):
        return top_level_summaries
    return [top_level_summaries]
