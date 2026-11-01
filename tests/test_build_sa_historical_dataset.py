import csv
import json

import pytest
from openpyxl import Workbook

from scripts.build_sa_historical_dataset import build_dataset, identifier_key


STATION_HEADERS = [
    "SAMPLE STATION ID", "POINT ID", "RIVER OR LAKE/DAM",
    "BRIEF LOCALITY DESCRIPTION OF SAMPLE STATION",
    "SOUTH LAT. DECIMAL DEGR", "SOUTH LON. DECIMAL DEGR",
    "TOTAL NUMBER OF SAMPLES", "FIRST SAMPLE DATE", "LAST SAMPLE DATE",
    "SAMPLE DRAINAGE REGION",
]


def write_station_workbook(path, duplicate_point=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sample stations with ID"
    sheet.append(STATION_HEADERS)
    sheet.append(["ST01", 1001, "RIVER", "Test River", -25.1, 28.2, 2,
                  "2000-01-01", "2001-01-01", "A10"])
    if duplicate_point:
        sheet.append(["ST02", 1001, "RIVER", "Duplicate point", -25.2, 28.3,
                      1, "2000-01-01", "2000-01-01", "A10"])
    for name in ("Samples stations with Z-ID", "Sample stations without ID"):
        workbook.create_sheet(name).append(STATION_HEADERS)
    workbook.save(path)


def write_chemistry_workbook(path, sheet_name, station_id, point_id, sentinel=-9999):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(["group"] * 8)
    sheet.append(["id", "id", "date", "year", "mS/m", "pH units", "mg/L", "mg/L"])
    sheet.append(["SAMPLE STATION ID", "POINT ID", "DATE", "YEAR", "EC", "PH", "TDS", "Na"])
    sheet.append([station_id, point_id, "2000-01-02", 2000, 100, 7.2, sentinel, 12])
    sheet.append([station_id, point_id, "2000-01-02", 2000, 100, 7.2, sentinel, 12])
    workbook.save(path)


def make_inputs(tmp_path, duplicate_station=False):
    stations = tmp_path / "stations.xlsx"
    rivers = tmp_path / "rivers.xlsx"
    dams = tmp_path / "dams.xlsx"
    write_station_workbook(stations, duplicate_station)
    write_chemistry_workbook(rivers, "Rivers", "ST01", 1001)
    write_chemistry_workbook(dams, "Dams & Lakes", "DAM01", 2002)
    return stations, rivers, dams


def test_identifier_key_normalizes_excel_numeric_ids_and_null_markers():
    assert identifier_key(1001.0) == "1001"
    assert identifier_key("1001.0") == "1001"
    assert identifier_key(" N/A ") is None
    assert identifier_key(None) is None


def test_builds_combined_dataset_and_audit_without_mutating_sources(tmp_path):
    stations, rivers, dams = make_inputs(tmp_path)
    original_hashes = [path.read_bytes() for path in (stations, rivers, dams)]
    output = tmp_path / "combined.csv"
    report_path = tmp_path / "audit.json"

    report = build_dataset(stations, rivers, dams, output, report_path)
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 4
    assert rows[0]["waterbody_type"] == "river"
    assert rows[0]["station_match_status"] == "matched_unique_point_id"
    assert rows[0]["station_locality"] == "Test River"
    assert rows[0]["latitude_decimal_degrees"] == "-25.1"
    assert rows[0]["tds"] == ""
    assert rows[0]["na"] == "12"
    assert rows[2]["station_match_status"] == "point_id_not_found"
    assert report["combined"]["output_rows"] == 4
    assert report["datasets"]["river"]["exact_duplicate_rows_after_first"] == 1
    assert report["datasets"]["dam_lake"]["station_unmatched_rows"] == 2
    assert report["datasets"]["dam_lake"]["missing_sentinel_counts_by_measurement"]["tds"] == 2
    assert json.loads(report_path.read_text())["combined"]["output_sha256"] == report["combined"]["output_sha256"]
    assert [path.read_bytes() for path in (stations, rivers, dams)] == original_hashes


def test_ambiguous_station_point_ids_are_not_joined(tmp_path):
    stations, rivers, dams = make_inputs(tmp_path, duplicate_station=True)
    report = build_dataset(stations, rivers, dams, tmp_path / "combined.csv", tmp_path / "audit.json")
    assert report["station_index"]["station_point_ids_ambiguous"] == 1
    assert report["datasets"]["river"]["station_ambiguous_rows"] == 2


def test_rejects_missing_worksheet_and_input_overwrite(tmp_path):
    stations, rivers, dams = make_inputs(tmp_path)
    bad_stations = tmp_path / "bad_stations.xlsx"
    workbook = Workbook()
    workbook.active.title = "wrong sheet"
    workbook.save(bad_stations)
    with pytest.raises(ValueError, match="missing expected worksheets"):
        build_dataset(bad_stations, rivers, dams, tmp_path / "out.csv", tmp_path / "report.json")
    with pytest.raises(ValueError, match="must not overwrite"):
        build_dataset(stations, rivers, dams, stations, tmp_path / "report.json")
