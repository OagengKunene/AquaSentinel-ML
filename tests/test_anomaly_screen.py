import numpy as np
import pandas as pd
import pytest

from scripts.anomaly_screen import analyse, robust_z_scores, screen_group


def test_robust_z_scores_detect_extreme_value():
    values = pd.Series([10, 10, 11, 9, 10, 10, 50], dtype=float)
    scores = robust_z_scores(values)
    assert abs(scores[-1]) > 3.5


def test_zero_mad_abstains_instead_of_infinite_scores():
    scores = robust_z_scores(pd.Series([4, 4, 4, 4, 40], dtype=float))
    assert np.isnan(scores).all()


def test_site_scoped_screening_keeps_sites_separate():
    frame = pd.DataFrame({
        "CharacteristicName": ["pH"] * 40,
        "ResultMeasure/MeasureUnitCode": ["std units"] * 40,
        "MonitoringLocationIdentifier": ["SITE-A"] * 20 + ["SITE-B"] * 20,
        "ResultMeasureValue": [7.0] * 19 + [12.0] + [8.0] * 20,
        "ActivityIdentifier": [f"sample-{i}" for i in range(40)],
    })
    result, report = analyse(frame, scope="site", min_samples=10)
    assert len(report["groups"]) == 2
    assert all(group["group"][-1] in ("SITE-A", "SITE-B") for group in report["groups"])
    assert set(result["aqua_group_status"]) == {"screened"}


def test_small_groups_are_skipped():
    frame = pd.DataFrame({
        "CharacteristicName": ["pH"] * 5,
        "ResultMeasure/MeasureUnitCode": ["std units"] * 5,
        "MonitoringLocationIdentifier": ["SITE-A"] * 5,
        "ResultMeasureValue": [6, 7, 7, 8, 9],
    })
    result, report = analyse(frame, scope="site", min_samples=10)
    assert report["groups_skipped"] == 1
    assert not result["aqua_robust_flag"].any()


def test_missing_required_measurement_columns_raise():
    with pytest.raises(ValueError):
        analyse(pd.DataFrame({"CharacteristicName": ["pH"]}))
