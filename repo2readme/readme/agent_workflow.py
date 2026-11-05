import logging

from repo2readme.readme.readme_generator import generate_readme
from repo2readme.readme.reviewer_agent import readme_reviewer

logger = logging.getLogger(__name__)

UNREVIEWED_SCORE = 0.0


def choose_best(
    best_readme: str, best_score: float, candidate: str, score: float
) -> tuple[str, float]:
    if not best_readme.strip() or score > best_score:
        return candidate, score
    return best_readme, best_score


def generate_readme_with_review(
    summaries,
    tree_structure,
    dependency_overview,
    settings,
    reviewer_settings,
    max_iterations=3,
):
    best_readme = ""
    best_score = UNREVIEWED_SCORE
    feedback = []
    drafts = []

    for _ in range(max_iterations):
        readme = generate_readme(
            summaries=summaries,
            tree_structure=tree_structure,
            feedback=feedback,
            latest_readme=drafts[-1] if drafts else "",
            provider=settings.provider,
            model_name=settings.model,
            base_url=settings.base_url,
            dependency_overview=dependency_overview,
        )
        drafts.append(readme)

        try:
            review = readme_reviewer(
                readme,
                provider=reviewer_settings.provider,
                model_name=reviewer_settings.model,
                base_url=reviewer_settings.base_url,
            )
        except Exception as exc:
            logger.warning("README review failed, keeping the current draft: %s", exc)
            best_readme, best_score = choose_best(
                best_readme, best_score, readme, UNREVIEWED_SCORE
            )
            break

        best_readme, best_score = choose_best(
            best_readme, best_score, readme, review.score
        )
        feedback.append(review.feedback)

        if review.score >= 8.5:
            break

    return {"best_readme": best_readme, "readme": drafts}
