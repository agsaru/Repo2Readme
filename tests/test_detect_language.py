from repo2readme.utils.detect_language import detect_lang


def test_detect_lang_with_extension_only():
    assert detect_lang(".py") == "python"
    assert detect_lang(".js") == "javascript"
    assert detect_lang(".cpp") == "cpp"
    assert detect_lang(".md") == "markdown"
    assert detect_lang(".json") == "json"


def test_detect_lang_with_path():
    assert detect_lang("main.py") == "python"
    assert detect_lang("index.js") == "javascript"
    assert detect_lang("src/config.yaml") == "yaml"


def test_detect_lang_unknown():
    assert detect_lang(".unknown") == "unknown"
    assert detect_lang("README") == "unknown"
    assert detect_lang(".txt") == "unknown"