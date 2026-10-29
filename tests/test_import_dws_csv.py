import json

import pandas as pd
import pytest

from scripts.import_dws_csv import audit_dws_csv, load_mapping, suggest_columns


def test_suggest_columns_is_review_only_and_supports_common_headers():
    columns = ["Monitoring Point Code", "Sample Date", "Determinant", "Result", "Units"]
    suggestions = suggest_columns(columns)
    assert suggestions["station_id"] == ["Monitoring Point Code"]
    assert suggestions["sample_datetime"] == ["Sample Date"]
    assert suggestions["parameter_name"] == ["Determinant"]
    assert suggestions["result_value"] == ["Result"]
    assert suggestions["result_unit"] == ["Units"]


def test_audit_only_writes_provenance_and_does_not_normalize(tmp_path):
    source = tmp_path / "dws_export.csv"
    pd.DataFrame({
        "Monitoring Point Code": ["A1", "A2"],
        "Sample Date": ["2020-01-01", "2020-01-02"],
        "Determinant": ["pH", "Electrical conductivity"],
        "Result": ["7.1", "120"],
        "Units": ["pH units", "mS/m"],
    }).to_csv(source, index=False)
    report = audit_dws_csv(source)
    saved = json.loads((tmp_path / "dws_export.csv.audit.json").read_text())
    assert report["row_count"] == 2
    assert report["normalized_output"] is None
    assert len(report["source_file_sha256"]) == 64
    assert saved["source_file_sha256"] == report["source_file_sha256"]
    assert report["suggested_mapping_only_review_required"]["station_id"] == ["Monitoring Point Code"]


def test_explicit_mapping_normalizes_and_retains_raw_columns_and_units(tmp_path):
    source = tmp_path / "dws_export.csv"
    mapping_path = tmp_path / "mapping.json"
    output = tmp_path / "normalized.csv"
    pd.DataFrame({
        "Monitoring Point Code": ["A1", "A1", ""],
        "Sample Date": ["2020-01-01", "not-a-date", "2020-01-03"],
        "Determinant": ["pH", "pH", "Nitrate"],
        "Result": ["7.1", "bad-value", "2.4"],
        "Units": ["pH units", "pH units", "mg/L"],
        "Lab Method": ["M1", "M1", "M2"],
    }).to_csv(source, index=False)
    mapping_path.write_text(json.dumps({
        "station_id": "Monitoring Point Code",
        "sample_datetime": "Sample Date",
        "parameter_name": "Determinant",
        "result_value": "Result",
        "result_unit": "Units",
        "method": "Lab Method",
    }))
    report = audit_dws_csv(source, mapping_path, output)
    normalized = pd.read_csv(output, dtype=str, keep_default_na=False)
    assert len(normalized) == 3
    assert normalized.loc[0, "station_id"] == "A1"
    assert normalized.loc[0, "result_unit"] == "pH units"
    assert normalized.loc[2, "result_unit"] == "mg/L"
    assert normalized.loc[0, "raw__Determinant"] == "pH"
    assert report["normalization_status_counts"]["ready_for_review"] == 1
    assert report["normalization_status_counts"]["invalid_or_missing_sample_datetime"] == 1
    assert report["normalization_status_counts"]["invalid_or_missing_numeric_result"] == 1


def test_mapping_requires_exact_existing_headers(tmp_path):
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps({
        "station_id": "site",
        "sample_datetime": "date",
        "parameter_name": "parameter",
        "result_value": "value",
        "result_unit": "unit",
    }))
    with pytest.raises(ValueError, match="do not exist"):
        load_mapping(mapping_path, ["Site", "Date", "Parameter", "Value", "Unit"])


def test_audit_rejects_empty_and_oversized_files(tmp_path, monkeypatch):
    source = tmp_path / "empty.csv"
    source.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        audit_dws_csv(source)
