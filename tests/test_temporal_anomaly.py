import numpy as np
import pandas as pd
import pytest

from scripts.temporal_anomaly import temporal_screen


def make_series(values, dates=None, sites=None):
    count = len(values)
    if dates is None:
        dates = pd.date_range("2024-01-01", periods=count, freq="D").astype(str)
    if sites is None:
        sites = ["SITE-A"] * count
    return pd.DataFrame({
        "MonitoringLocationIdentifier": sites,
        "CharacteristicName": ["pH"] * count,
        "ResultMeasure/MeasureUnitCode": ["std units"] * count,
        "ResultMeasureValue": values,
        "ActivityStartDate": dates,
    })


def test_temporal_screen_flags_outlier_against_prior_history_only():
    values = [7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 12.0]
    frame = make_series(values)
    result, report = temporal_screen(frame, min_history=20, lookback=30)
    assert bool(result.iloc[-1]["aqua_temporal_flag"])
    assert result.iloc[-1]["aqua_temporal_history_count"] == 20
    assert report["flagged_rows"] == 1


def test_same_timestamp_rows_do_not_leak_into_each_others_baseline():
    base_dates = list(pd.date_range("2024-01-01", periods=20, freq="D").astype(str))
    dates = base_dates + ["2024-01-21", "2024-01-21"]
    values = [7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 6.9, 7.0, 7.1, 12.0, 11.5]
    result, _ = temporal_screen(make_series(values, dates), min_history=20)
    assert result.iloc[-2]["aqua_temporal_history_count"] == 20
    assert result.iloc[-1]["aqua_temporal_history_count"] == 20


def test_temporal_groups_are_site_specific():
    values = [7.0] * 20 + [12.0] + [8.0] * 20 + [12.0]
    sites = ["SITE-A"] * 21 + ["SITE-B"] * 21
    result, _ = temporal_screen(make_series(values, sites=sites), min_history=20)
    assert bool(result.iloc[20]["aqua_temporal_flag"])
    assert not bool(result.iloc[-1]["aqua_temporal_flag"])


def test_zero_mad_abstains():
    values = [7.0] * 20 + [12.0]
    result, _ = temporal_screen(make_series(values), min_history=20)
    assert result.iloc[-1]["aqua_temporal_status"] == "zero_mad_abstained"
    assert np.isnan(result.iloc[-1]["aqua_temporal_robust_z"])


def test_invalid_dates_are_marked():
    dates = ["not-a-date"] + list(pd.date_range("2024-01-01", periods=4, freq="D").astype(str))
    result, report = temporal_screen(make_series([7, 7, 7, 7, 7], dates), min_history=3)
    assert result.iloc[0]["aqua_temporal_status"] == "missing_or_invalid_timestamp"
    assert report["invalid_timestamp_rows"] == 1


def test_required_temporal_columns_must_exist():
    with pytest.raises(ValueError):
        temporal_screen(pd.DataFrame({"ResultMeasureValue": [1]}))
