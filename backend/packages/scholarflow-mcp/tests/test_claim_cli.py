import json

from scholarflow_mcp import claim_cli


def test_claim_cli_writes_assessment_output(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"pages": [], "claims": []}), encoding="utf-8")
    output_path = tmp_path / "result.json"

    async def fake_assessment(*, pages, claims):
        assert pages == []
        assert claims == []
        return {"claims": [], "summary": {"claim_count": 0}, "scope": "test"}

    monkeypatch.setattr(claim_cli, "assess_claim_evidence", fake_assessment)

    exit_code = claim_cli.main([str(input_path), "--output", str(output_path)])

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["scope"] == "test"
