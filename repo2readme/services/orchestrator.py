import logging

from repo2readme.llm.settings import LLMSettings, resolve_settings
from repo2readme.readme.agent_workflow import build_workflow
from repo2readme.readme.postprocess import postprocess_readme

logger = logging.getLogger(__name__)

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
        "latest_readme": "",
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

    readme, issues = postprocess_readme(final_state['best_readme'])

    for issue in issues:
        logger.warning("README %s: %s", issue.kind, issue.message)

    return readme
