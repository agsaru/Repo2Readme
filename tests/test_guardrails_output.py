import pytest

from repo2readme.guardrails import redact_secrets, validate_readme_output


def test_generated_readme_is_trimmed_and_secrets_are_redacted():
    result = validate_readme_output(
        "# Demo\n\nAPI_KEY=\\"sk_test_super_secret_value\\"\n"
    )

    assert result.startswith("# Demo")
    assert "sk_test_super_secret_value" not in result
    assert "[REDACTED]" in result


@pytest.mark.parametrize("value", ["", "  \n", None, 123])
def test_empty_or_non_text_readme_output_is_rejected(value):
    with pytest.raises(ValueError, match="empty output"):
        validate_readme_output(value)


def test_redaction_does_not_change_environment_variable_references():
    value = 'API_KEY="$API_KEY"'
    assert redact_secrets(value) == value
