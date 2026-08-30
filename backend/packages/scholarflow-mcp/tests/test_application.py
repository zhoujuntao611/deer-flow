import pytest

from scholarflow_mcp.application import normalize_provider_names, timeout_seconds


def test_provider_names_are_validated_and_deduplicated() -> None:
    assert normalize_provider_names(["OpenAlex", "arxiv", "openalex"]) == ["openalex", "arxiv"]

    with pytest.raises(ValueError, match="unknown providers: scholar"):
        normalize_provider_names(["scholar"])


def test_timeout_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHOLARFLOW_HTTP_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError, match="between 1 and 120"):
        timeout_seconds()

    monkeypatch.setenv("SCHOLARFLOW_HTTP_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValueError, match="must be numeric"):
        timeout_seconds()
