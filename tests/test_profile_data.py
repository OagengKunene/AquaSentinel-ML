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
