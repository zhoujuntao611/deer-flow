import json

from scholarflow_mcp import cli


def _payload(status: str = "ok") -> dict:
    return {
        "query": "verified agents",
        "records": [],
        "provider_status": [
            {
                "provider": "openalex",
                "status": status,
                "record_count": 0,
                "error": None if status == "ok" else "offline",
            }
        ],
        "total_raw_records": 0,
        "unique_before_limit": 0,
        "unique_records": 0,
        "duplicates_removed": 0,
    }


def test_cli_writes_machine_readable_json(monkeypatch, tmp_path) -> None:
    async def fake_search(*args, **kwargs):
        assert args == ("verified agents",)
        assert kwargs["providers"] == ["openalex"]
        return _payload()

    monkeypatch.setattr(cli, "run_search", fake_search)
    output = tmp_path / "result.json"

    exit_code = cli.main(["verified agents", "--providers", "openalex", "--output", str(output), "--compact"])

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["query"] == "verified agents"


def test_cli_returns_nonzero_when_every_provider_fails(monkeypatch, capsys) -> None:
    async def fake_search(*args, **kwargs):
        return _payload(status="error")

    monkeypatch.setattr(cli, "run_search", fake_search)

    assert cli.main(["query"]) == 2
    assert json.loads(capsys.readouterr().out)["provider_status"][0]["status"] == "error"


def test_cli_preserves_unicode_output(monkeypatch, capsys) -> None:
    payload = _payload()
    payload["records"] = [{"title": "GNSS−IMU 融合"}]

    async def fake_search(*args, **kwargs):
        return payload

    monkeypatch.setattr(cli, "run_search", fake_search)

    assert cli.main(["query", "--compact"]) == 0
    assert json.loads(capsys.readouterr().out)["records"][0]["title"] == "GNSS−IMU 融合"
