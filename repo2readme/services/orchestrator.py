import logging

from repo2readme.llm.settings import LLMSettings, resolve_settings
from repo2readme.readme.agent_workflow import build_workflow
from repo2readme.readme.postprocess import postprocess_readme

logger = logging.getLogger(__name__)


class ReadmeGenerationError(RuntimeError):
    """The pipeline finished without producing a README worth writing.

    Raised instead of returning an empty string, because the caller's next step
    is to write the result over the user's ``README.md``.
    """


def run_pipeline(
    summaries: list,
    tree: str,
    dependency_overview: str,
    settings: LLMSettings | None = None,
    reviewer_settings: LLMSettings | None = None,
) -> str:
    """
    Invokes the LangGraph workflow to generate the README and returns the result.

    ``settings`` is the provider, model and base URL the run already resolved;
    the generator and the reviewer both use it unless ``reviewer_settings``
    says otherwise. Taking resolved settings - rather than the raw CLI strings
    this used to take - is what stops the two steps from applying different
    defaults and calling two different vendors with the same ``--model``.

    The model's answer is normalized (wrapping code fence removed, trailing
    whitespace and blank line runs cleaned up) before being returned, and any
    structural problem that cannot be fixed mechanically - a table of contents
    pointing at a heading that no longer exists, a placeholder image - is
    logged as a warning rather than silently rewritten.

    Raises
    ------
    ReadmeGenerationError
        If the workflow produced no usable README. An empty result used to be
        returned like any other, and the CLI wrote it straight over the user's
        file while reporting success.
    """
    settings = settings or resolve_settings()
    reviewer_settings = reviewer_settings or settings

    logger.debug(
        "Generating README with %s, reviewing with %s",
        settings.describe(),
        reviewer_settings.describe(),
    )

    workflow = build_workflow()

    initial_state = {
        "summaries": summaries,
        "tree_structure": tree,
        "iteration_no": 0,
        "max_iterations": 3,
        'best_score': 0.0,
        "best_readme": "",
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "reviewer_provider": reviewer_settings.provider,
        "reviewer_model": reviewer_settings.model,
        "reviewer_base_url": reviewer_settings.base_url,
        "dependency_overview": dependency_overview,
    }

    final_state = workflow.invoke(initial_state)

    # Empty entries mark the iterations whose review came back normally.
    for error in final_state.get("review_errors") or []:
        if error:
            logger.warning("README review did not complete: %s", error)

    readme, issues = postprocess_readme(select_readme(final_state))

    for issue in issues:
        logger.warning("README %s: %s", issue.kind, issue.message)

    if any(issue.kind == "empty" for issue in issues):
        raise ReadmeGenerationError(
            "The model returned no README content, so there is nothing to write."
        )

    return readme


def select_readme(final_state: dict) -> str:
    """Return the draft to keep from a finished workflow state.

    Normally the highest scoring draft. The last draft generated is the
    fallback: the scored draft is only recorded by the reviewer node, so
    anything that stops the graph before it runs would otherwise discard work
    that is perfectly usable.
    """
    best = (final_state.get("best_readme") or "").strip()
    if best:
        return final_state["best_readme"]

    drafts = final_state.get("readme") or []
    for draft in reversed(drafts):
        if draft and draft.strip():
            return draft

    return ""
