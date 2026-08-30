"""The generate/review loop must never hand back nothing.

Two ways it used to:

* the loop only adopted a draft that beat ``best_score``, which starts at
  ``0.0`` alongside an empty ``best_readme``, so a first draft the reviewer
  scored ``0`` lost against nothing and the run returned ``""``;
* the reviewer re-raised after its retries were exhausted, and nothing between
  it and the CLI caught that, so one failed review discarded every draft.

Either way the CLI wrote the result over the user's README.md and printed a
green success line.
"""

import pytest
from langgraph.graph import END

from repo2readme.readme import agent_workflow
from repo2readme.readme.agent_workflow import (
    UNREVIEWED_SCORE,
    choose_best,
    latest_review_error,
    readme_condition,
)
from repo2readme.readme.reviewer_agent import ReviewSchema
from repo2readme.services.orchestrator import (
    ReadmeGenerationError,
    run_pipeline,
    select_readme,
)

DRAFT = "# Project\n\nA real README with real content.\n"
BETTER_DRAFT = "# Project\n\nA better README, with installation notes.\n"


def _pipeline():
    # The provider, model and base URL are resolved once by the caller and
    # handed down as settings; passing none leaves run_pipeline to resolve the
    # defaults, which is what these tests want.
    return run_pipeline(
        summaries=["a summary"],
        tree="repo/",
        dependency_overview="",
        settings=None,
        reviewer_settings=None,
    )


class Reviewer:
    """Reviewer stub returning a scripted sequence of scores or failures."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, readme, **_kwargs):
        self.calls += 1
        outcome = self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return ReviewSchema(score=outcome, feedback=f"feedback {self.calls}")


class Generator:
    """Generator stub returning a scripted sequence of drafts."""

    def __init__(self, *drafts):
        self.drafts = list(drafts)
        self.calls = 0

    def __call__(self, **_kwargs):
        self.calls += 1
        return self.drafts[min(self.calls - 1, len(self.drafts) - 1)]


@pytest.fixture
def wire(monkeypatch):
    def _wire(generator, reviewer):
        monkeypatch.setattr(agent_workflow, "generate_readme", generator)
        monkeypatch.setattr(agent_workflow, "readme_reviewer", reviewer)
        return generator, reviewer

    return _wire


class TestChooseBest:
    def test_first_draft_is_adopted_even_with_a_zero_score(self):
        assert choose_best("", 0.0, DRAFT, 0.0) == (DRAFT, 0.0)

    def test_first_draft_is_adopted_with_a_negative_score(self):
        # The schema says 1-10, but nothing enforces what the model returns.
        assert choose_best("", 0.0, DRAFT, -3.0) == (DRAFT, -3.0)

    def test_a_higher_score_replaces_the_incumbent(self):
        assert choose_best(DRAFT, 4.0, BETTER_DRAFT, 7.5) == (BETTER_DRAFT, 7.5)

    def test_a_lower_score_keeps_the_incumbent(self):
        assert choose_best(BETTER_DRAFT, 7.5, DRAFT, 2.0) == (BETTER_DRAFT, 7.5)

    def test_an_equal_score_keeps_the_incumbent(self):
        assert choose_best(DRAFT, 7.5, BETTER_DRAFT, 7.5) == (DRAFT, 7.5)

    def test_a_whitespace_only_incumbent_counts_as_no_draft(self):
        assert choose_best("   \n ", 9.9, DRAFT, 1.0) == (DRAFT, 1.0)


class TestSelectReadme:
    def test_prefers_the_best_scoring_draft(self):
        state = {"best_readme": BETTER_DRAFT, "readme": [DRAFT, BETTER_DRAFT]}
        assert select_readme(state) == BETTER_DRAFT

    def test_falls_back_to_the_last_non_empty_draft(self):
        state = {"best_readme": "", "readme": [DRAFT, "   "]}
        assert select_readme(state) == DRAFT

    def test_returns_empty_when_there_is_nothing_at_all(self):
        assert select_readme({"best_readme": "", "readme": []}) == ""

    def test_tolerates_a_state_without_the_keys(self):
        assert select_readme({}) == ""


class TestZeroScoredDraft:
    def test_a_draft_scored_zero_is_still_returned(self, wire):
        generator, reviewer = wire(Generator(DRAFT), Reviewer(0.0))

        result = _pipeline()

        assert result.strip() == DRAFT.strip()
        # A low score still means "try to improve", so the loop runs its three
        # iterations; what changed is that the draft is no longer thrown away.
        assert generator.calls == 3
        assert reviewer.calls == 3

    def test_the_loop_still_iterates_towards_a_better_draft(self, wire):
        generator, _reviewer = wire(
            Generator(DRAFT, BETTER_DRAFT), Reviewer(0.0, 9.0)
        )

        result = _pipeline()

        assert result.strip() == BETTER_DRAFT.strip()
        assert generator.calls == 2

    def test_the_highest_scoring_draft_wins_not_the_last_one(self, wire):
        wire(Generator(BETTER_DRAFT, DRAFT, DRAFT), Reviewer(8.0, 2.0, 1.0))

        assert _pipeline().strip() == BETTER_DRAFT.strip()


class TestReviewerFailure:
    def test_a_failed_review_keeps_the_draft(self, wire):
        _generator, reviewer = wire(
            Generator(DRAFT), Reviewer(RuntimeError("429 rate limit"))
        )

        result = _pipeline()

        assert result.strip() == DRAFT.strip()
        assert reviewer.calls == 1

    def test_a_failed_review_ends_the_loop_instead_of_re_asking(self, wire):
        # Without feedback there is nothing for another round to improve on.
        generator, _reviewer = wire(
            Generator(DRAFT, BETTER_DRAFT), Reviewer(RuntimeError("boom"))
        )

        _pipeline()

        assert generator.calls == 1

    def test_a_failed_review_does_not_lose_an_earlier_better_draft(self, wire):
        wire(
            Generator(BETTER_DRAFT, DRAFT),
            Reviewer(6.0, RuntimeError("boom")),
        )

        assert _pipeline().strip() == BETTER_DRAFT.strip()

    def test_the_failure_is_logged(self, wire, caplog):
        wire(Generator(DRAFT), Reviewer(RuntimeError("503 service unavailable")))

        with caplog.at_level("WARNING"):
            _pipeline()

        assert any(
            "503 service unavailable" in record.getMessage()
            for record in caplog.records
        )

    def test_the_unreviewed_score_never_beats_a_reviewed_draft(self):
        assert choose_best(DRAFT, 1.0, BETTER_DRAFT, UNREVIEWED_SCORE) == (DRAFT, 1.0)


class TestLoopCondition:
    """``review_errors`` accumulates, so only its last entry is current."""

    def _state(self, review_errors, score=5.0, iteration=1):
        return {
            "score": [score],
            "iteration_no": iteration,
            "max_iterations": 3,
            "review_errors": review_errors,
        }

    def test_no_error_recorded_yet_keeps_iterating(self):
        assert readme_condition(self._state([])) == "generate_readme"

    def test_a_successful_review_keeps_iterating(self):
        assert readme_condition(self._state([""])) == "generate_readme"

    def test_a_failed_review_ends_the_loop(self):
        assert readme_condition(self._state(["boom"])) == END

    def test_an_earlier_failure_does_not_end_a_recovered_run(self):
        assert readme_condition(self._state(["boom", ""])) == "generate_readme"

    def test_the_latest_failure_ends_the_loop(self):
        assert readme_condition(self._state(["", "boom"])) == END

    def test_a_high_score_still_ends_the_loop(self):
        assert readme_condition(self._state([""], score=9.0)) == END

    def test_the_iteration_cap_still_ends_the_loop(self):
        assert readme_condition(self._state([""], iteration=3)) == END

    def test_a_missing_channel_is_tolerated(self):
        state = {"score": [5.0], "iteration_no": 1, "max_iterations": 3}

        assert readme_condition(state) == "generate_readme"


class TestLatestReviewError:
    def test_empty_history(self):
        assert latest_review_error({"review_errors": []}) == ""

    def test_missing_channel(self):
        assert latest_review_error({}) == ""

    def test_returns_the_last_entry(self):
        assert latest_review_error({"review_errors": ["a", "", "b"]}) == "b"

    def test_a_successful_review_reads_as_no_error(self):
        assert latest_review_error({"review_errors": ["a", ""]}) == ""


class TestReviewErrorLogging:
    def test_successful_iterations_are_not_logged_as_failures(self, wire, caplog):
        wire(Generator(DRAFT), Reviewer(9.0))

        with caplog.at_level("WARNING"):
            _pipeline()

        assert not any(
            "review did not complete" in record.getMessage()
            for record in caplog.records
        )


class TestEmptyResult:
    def test_an_empty_generation_raises_instead_of_returning_nothing(self, wire):
        wire(Generator(""), Reviewer(0.0))

        with pytest.raises(ReadmeGenerationError):
            _pipeline()

    def test_a_whitespace_only_generation_raises(self, wire):
        wire(Generator("   \n\n  "), Reviewer(5.0))

        with pytest.raises(ReadmeGenerationError):
            _pipeline()

    def test_the_error_message_says_nothing_was_produced(self, wire):
        wire(Generator(""), Reviewer(5.0))

        with pytest.raises(ReadmeGenerationError, match="no README content"):
            _pipeline()

    def test_a_normal_run_is_unaffected(self, wire):
        wire(Generator(DRAFT), Reviewer(9.0))

        assert _pipeline().strip() == DRAFT.strip()


class TestCliDoesNotWriteAnEmptyReadme:
    def test_an_existing_readme_is_left_alone_and_the_run_fails(
        self, tmp_path, monkeypatch
    ):
        import importlib

        from click.testing import CliRunner

        cli_main = importlib.import_module("repo2readme.cli.main")

        # run() resolves its cache directory from the working directory and
        # flushes it in a finally block, so keep that out of the checkout.
        monkeypatch.chdir(tmp_path)

        target = tmp_path / "README.md"
        target.write_text("# Existing content the user cares about\n")

        monkeypatch.setattr(
            cli_main,
            "run_pipeline",
            lambda **_kwargs: (_ for _ in ()).throw(
                ReadmeGenerationError("The model returned no README content")
            ),
        )
        # Takes the resolved generator and reviewer settings, not a
        # provider name.
        monkeypatch.setattr(cli_main, "setup_api_keys", lambda *_settings: None)
        monkeypatch.setattr(
            cli_main, "generate_all_summaries", lambda **_kwargs: ([{"a": 1}], [])
        )
        monkeypatch.setattr(
            cli_main, "generate_hierarchical_summaries", lambda **_kwargs: [{"a": 1}]
        )

        source = tmp_path / "repo"
        source.mkdir()
        (source / "main.py").write_text("print('hello')\n")

        result = CliRunner().invoke(
            cli_main.main,
            ["run", "--local", str(source), "--output", str(target), "--force"],
        )

        assert result.exit_code == 1
        assert target.read_text() == "# Existing content the user cares about\n"
        assert "Nothing was written" in result.output
