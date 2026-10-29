import pandas as pd
import pytest

from scripts.profile_data import profile_csv


def test_profile_reports_missingness_duplicates_and_target(tmp_path):
    path = tmp_path / "benchmark.csv"
    pd.DataFrame({
        "ph": [6.5, 7.0, 7.0],
        "Hardness": [100, 110, 110],
        "Potability": [0, 1, 1],
    }).to_csv(path, index=False)

    report = profile_csv(str(path), "Potability")
    assert report["rows"] == 3
    assert report["duplicate_rows"] == 1
    assert report["missing_counts"]["ph"] == 0
    assert report["target_distribution"] == {"1": 2, "0": 1}


def test_profile_rejects_missing_target(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"value": [1, 2]}).to_csv(path, index=False)
    with pytest.raises(ValueError):
        profile_csv(str(path), "Potability")


def test_profile_cli_writes_valid_json(tmp_path, monkeypatch):
    import json
    import sys

    from scripts import profile_data

    source = tmp_path / "input.csv"
    output = tmp_path / "profile.json"
    pd.DataFrame({"ph": [6.5, 7.0, 7.5]}).to_csv(source, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["profile_data", "--data", str(source), "--output", str(output)],
    )

    profile_data.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["rows"] == 3
