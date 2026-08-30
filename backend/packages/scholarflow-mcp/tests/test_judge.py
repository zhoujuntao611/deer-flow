import json

import httpx
import pytest

from scholarflow_mcp.judge import JudgeConfig, OpenAIResponsesJudge, normalize_judge_cases, validate_verdicts


def _case() -> list[dict]:
    return [
        {
            "claim_id": "claim-1",
            "claim_text": "The detector reached 94% accuracy.",
            "evidence_spans": [{"span_id": "span-1", "text": "The detector reached 94% accuracy."}],
        }
    ]


@pytest.mark.asyncio
async def test_responses_judge_uses_strict_schema_and_validates_citations() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload["text"]["format"]["strict"] is True
        assert "untrusted data" in payload["instructions"]
        return httpx.Response(
            200,
            headers={"x-request-id": "request-1"},
            json={
                "id": "response-1",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "results": [
                                            {
                                                "claim_id": "claim-1",
                                                "label": "supported",
                                                "confidence": 0.92,
                                                "rationale": "The value and scope match.",
                                                "cited_span_ids": ["span-1"],
                                            }
                                        ]
                                    }
                                ),
                            }
                        ]
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        judge = OpenAIResponsesJudge(
            JudgeConfig(api_key="secret", model="test-model", endpoint="https://judge.test/v1/responses"),
            client=client,
        )
        result = await judge.classify(_case())

    assert result["results"][0]["label"] == "supported"
    assert result["judge"] == {
        "provider": "openai_responses",
        "model": "test-model",
        "response_id": "response-1",
        "request_id": "request-1",
    }


def test_rejects_unknown_citation_and_missing_claim() -> None:
    with pytest.raises(ValueError, match="unknown span IDs"):
        validate_verdicts(
            {
                "results": [
                    {
                        "claim_id": "claim-1",
                        "label": "supported",
                        "confidence": 0.8,
                        "rationale": "Rationale",
                        "cited_span_ids": ["invented-span"],
                    }
                ]
            },
            _case(),
        )

    with pytest.raises(ValueError, match="omitted claim IDs"):
        validate_verdicts({"results": []}, _case())


def test_normalize_cases_rejects_duplicate_ids_and_unbounded_evidence() -> None:
    with pytest.raises(ValueError, match="duplicate judge claim_id"):
        normalize_judge_cases(_case() + _case())
    oversized = _case()
    oversized[0]["evidence_spans"][0]["text"] = "x" * 20_001
    with pytest.raises(ValueError, match="at most 20000"):
        normalize_judge_cases(oversized)


def test_judge_config_requires_explicit_credentials_and_model(monkeypatch) -> None:
    for name in ("SCHOLARFLOW_JUDGE_API_KEY", "OPENAI_API_KEY", "SCHOLARFLOW_JUDGE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="API_KEY"):
        JudgeConfig.from_environment()

    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    with pytest.raises(ValueError, match="JUDGE_MODEL"):
        JudgeConfig.from_environment()
