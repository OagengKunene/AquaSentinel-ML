"""Build an auditable South African historical river/dam chemistry dataset.

The source workbooks are read-only. Chemistry records are retained in wide form,
joined to station metadata only on unique POINT IDs, and written with an audit
report. No unit conversion, imputation, aggregation, deduplication, or safety
classification is performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

STATION_SHEETS = (
    "Sample stations with ID",
    "Samples stations with Z-ID",
    "Sample stations without ID",
)
STATION_HEADER_ROW = 1
CHEMISTRY_HEADER_ROW = 3
SENTINEL_RE = re.compile(r"^-9999(?:\.0+)?$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def identifier_key(value: Any) -> str | None:
    """Normalize Excel numeric IDs without treating common null markers as IDs."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"n/a", "na", "nan", "none", "null"}:
        return None
    try:
        number = float(text)
        if math.isfinite(number) and number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    return text


def slug(value: Any, fallback: str) -> str:
    text = re.sub(r"\s+", " ", clean_text(value).replace("\n", " ").replace("\r", " ")).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or fallback


def unique_measurement_columns(headers: list[Any], units: list[Any]) -> tuple[list[str], list[dict[str, str]]]:
    names: list[str] = []
    metadata: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for index, header in enumerate(headers):
        base = slug(header, f"measurement_{index + 1}")
        counts[base] += 1
        name = base if counts[base] == 1 else f"{base}_{counts[base]}"
        unit = clean_text(units[index]) if index < len(units) else ""
        names.append(name)
        metadata.append({"output_column": name, "source_header": clean_text(header), "source_unit": unit})
    return names, metadata


def parse_date(value: Any) -> str:
    if value is None or clean_text(value) == "":
        return ""
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = clean_text(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text


def is_missing_sentinel(value: Any) -> bool:
    return value is not None and bool(SENTINEL_RE.fullmatch(clean_text(value)))


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return parse_date(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return format(value, ".15g")
    return str(value).strip()


def load_station_index(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any], set[str]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    index_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts = Counter()
    try:
        available = set(workbook.sheetnames)
        missing_sheets = [sheet for sheet in STATION_SHEETS if sheet not in available]
        if missing_sheets:
            raise ValueError(f"Station workbook is missing expected worksheets: {missing_sheets}")
        for sheet_name in STATION_SHEETS:
            sheet = workbook[sheet_name]
            headers = [clean_text(v) for v in next(sheet.iter_rows(min_row=STATION_HEADER_ROW, max_row=STATION_HEADER_ROW, values_only=True))]
            positions = {header: i for i, header in enumerate(headers) if header}
            point_pos = positions.get("POINT ID")
            if point_pos is None:
                raise ValueError(f"Worksheet {sheet_name!r} has no POINT ID column")
            for excel_row, values in enumerate(sheet.iter_rows(min_row=STATION_HEADER_ROW + 1, values_only=True), start=STATION_HEADER_ROW + 1):
                counts["station_rows_read"] += 1
                point_key = identifier_key(values[point_pos] if point_pos < len(values) else None)
                if point_key is None:
                    counts["station_rows_without_point_id"] += 1
                    continue
                row = {header: (values[pos] if pos < len(values) else None) for header, pos in positions.items()}
                row["_source_sheet"] = sheet_name
                row["_source_excel_row"] = excel_row
                index_rows[point_key].append(row)
    finally:
        workbook.close()

    unique_index: dict[str, dict[str, Any]] = {}
    ambiguous_keys: set[str] = set()
    for key, rows in index_rows.items():
        if len(rows) == 1:
            unique_index[key] = rows[0]
        else:
            ambiguous_keys.add(key)
    counts["station_point_ids_unique"] = len(index_rows)
    counts["station_point_ids_ambiguous"] = len(ambiguous_keys)
    counts["station_point_ids_joinable"] = len(unique_index)
    return unique_index, dict(counts), ambiguous_keys


def build_dataset(
    station_path: Path,
    rivers_path: Path,
    dams_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    inputs = (station_path, rivers_path, dams_path)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(f"Input workbook not found: {path}")
    resolved_inputs = {path.resolve() for path in inputs}
    if output_path.resolve() in resolved_inputs:
        raise ValueError("Output CSV must not overwrite an input workbook")
    if report_path.resolve() in resolved_inputs:
        raise ValueError("Audit report must not overwrite an input workbook")
    if output_path.resolve() == report_path.resolve():
        raise ValueError("Output CSV and audit report must be different files")

    station_index, station_counts, ambiguous_station_keys = load_station_index(station_path)
    report: dict[str, Any] = {
        "project": "AquaSentinel-ML South African historical water chemistry research pipeline",
        "source_files": {},
        "station_index": station_counts,
        "datasets": {},
        "combined": {},
        "processing_rules": [
            "Original XLSX workbooks are read-only and never modified.",
            "Chemistry field labels are read from Excel row 3; row 2 supplies source units.",
            "All source chemistry columns are retained in wide form with unique output column names.",
            "The -9999 missing-value sentinel is converted to an empty CSV cell and counted by field.",
            "No unit conversion, imputation, deduplication, aggregation, or regulatory classification is performed.",
            "Station metadata is joined only when POINT ID uniquely identifies one station row.",
            "Unmatched and ambiguous station joins are retained and explicitly labelled.",
        ],
        "interpretation_warning": (
            "Historical research data only. Statistical anomalies do not establish contamination, "
            "drinking-water safety, health risk, or regulatory exceedance. Check source metadata, "
            "measurement methods, units, detection limits, sampling context and reuse conditions."
        ),
    }
    for path, label in ((station_path, "stations"), (rivers_path, "rivers"), (dams_path, "dams_lakes")):
        report["source_files"][label] = {
            "file_name": path.name,
            "file_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    combined_counts = Counter()
    combined_sentinels: Counter[str] = Counter()
    output_fields: list[str] | None = None

    with output_path.open("w", encoding="utf-8-sig", newline="") as output_stream:
        writer = None
        reference_measurement_names: list[str] | None = None
        for workbook_path, kind, expected_sheet in (
            (rivers_path, "river", "Rivers"),
            (dams_path, "dam_lake", "Dams & Lakes"),
        ):
            workbook = load_workbook(workbook_path, read_only=True, data_only=True)
            try:
                if expected_sheet not in workbook.sheetnames:
                    raise ValueError(f"{workbook_path.name} is missing worksheet {expected_sheet!r}")
                sheet = workbook[expected_sheet]
                header_values = list(next(sheet.iter_rows(min_row=CHEMISTRY_HEADER_ROW, max_row=CHEMISTRY_HEADER_ROW, values_only=True)))
                unit_values = list(next(sheet.iter_rows(min_row=CHEMISTRY_HEADER_ROW - 1, max_row=CHEMISTRY_HEADER_ROW - 1, values_only=True)))
                measurement_names, measurement_metadata = unique_measurement_columns(header_values[4:], unit_values[4:])
                if reference_measurement_names is None:
                    reference_measurement_names = measurement_names
                elif measurement_names != reference_measurement_names:
                    raise ValueError("River and dams/lakes workbooks have different measurement field names or ordering")

                if output_fields is None:
                    output_fields = [
                        "waterbody_type", "source_workbook", "source_sheet", "source_excel_row",
                        "sample_station_id_source", "point_id_source", "sample_date", "sample_year",
                        "station_match_status", "station_sample_station_id", "station_waterbody_type",
                        "station_locality", "latitude_decimal_degrees", "longitude_decimal_degrees",
                        "drainage_region", "station_first_sample_date", "station_last_sample_date",
                    ] + measurement_names
                    writer = csv.DictWriter(output_stream, fieldnames=output_fields, extrasaction="ignore")
                    writer.writeheader()

                dataset_counts = Counter()
                sentinel_counts: Counter[str] = Counter()
                exact_seen: set[bytes] = set()
                repeated_event_counts: Counter[tuple[str, str, str]] = Counter()
                date_min = None
                date_max = None
                point_ids: set[str] = set()
                matched_point_ids: set[str] = set()
                unmatched_point_ids: set[str] = set()
                ambiguous_point_ids: set[str] = set()

                for excel_row, values_tuple in enumerate(
                    sheet.iter_rows(min_row=CHEMISTRY_HEADER_ROW + 1, values_only=True),
                    start=CHEMISTRY_HEADER_ROW + 1,
                ):
                    values = list(values_tuple)
                    if not values or all(value is None for value in values):
                        continue
                    dataset_counts["rows"] += 1
                    station_id = values[0] if len(values) > 0 else None
                    point_id = values[1] if len(values) > 1 else None
                    date_value = values[2] if len(values) > 2 else None
                    year_value = values[3] if len(values) > 3 else None
                    point_key = identifier_key(point_id)
                    if point_key:
                        point_ids.add(point_key)
                    station = station_index.get(point_key) if point_key else None
                    if station is not None:
                        dataset_counts["station_matched_rows"] += 1
                        matched_point_ids.add(point_key)
                        match_status = "matched_unique_point_id"
                    elif point_key and point_key in ambiguous_station_keys:
                        dataset_counts["station_ambiguous_rows"] += 1
                        ambiguous_point_ids.add(point_key)
                        match_status = "ambiguous_point_id_not_joined"
                    else:
                        dataset_counts["station_unmatched_rows"] += 1
                        if not point_key:
                            dataset_counts["missing_point_id_rows"] += 1
                        if point_key:
                            unmatched_point_ids.add(point_key)
                        match_status = "missing_point_id" if not point_key else "point_id_not_found"

                    parsed_date = parse_date(date_value)
                    if parsed_date:
                        try:
                            parsed_for_range = date.fromisoformat(parsed_date[:10])
                            date_min = parsed_for_range if date_min is None else min(date_min, parsed_for_range)
                            date_max = parsed_for_range if date_max is None else max(date_max, parsed_for_range)
                        except ValueError:
                            dataset_counts["invalid_date_rows"] += 1
                    else:
                        dataset_counts["missing_date_rows"] += 1
                    event_key = (identifier_key(station_id) or "", point_key or "", parsed_date)
                    repeated_event_counts[event_key] += 1
                    row_digest = hashlib.sha256("\x1f".join(csv_value(v) for v in values).encode("utf-8")).digest()
                    if row_digest in exact_seen:
                        dataset_counts["exact_duplicate_rows_after_first"] += 1
                    else:
                        exact_seen.add(row_digest)

                    row = {
                        "waterbody_type": kind,
                        "source_workbook": workbook_path.name,
                        "source_sheet": expected_sheet,
                        "source_excel_row": excel_row,
                        "sample_station_id_source": csv_value(station_id),
                        "point_id_source": csv_value(point_id),
                        "sample_date": parsed_date,
                        "sample_year": csv_value(year_value),
                        "station_match_status": match_status,
                        "station_sample_station_id": csv_value(station.get("SAMPLE STATION ID")) if station else "",
                        "station_waterbody_type": csv_value(station.get("RIVER OR LAKE/DAM")) if station else "",
                        "station_locality": csv_value(station.get("BRIEF LOCALITY DESCRIPTION OF SAMPLE STATION")) if station else "",
                        "latitude_decimal_degrees": csv_value(station.get("SOUTH LAT. DECIMAL DEGR")) if station else "",
                        "longitude_decimal_degrees": csv_value(station.get("SOUTH LON. DECIMAL DEGR")) if station else "",
                        "drainage_region": csv_value(station.get("SAMPLE DRAINAGE REGION")) if station else "",
                        "station_first_sample_date": parse_date(station.get("FIRST SAMPLE DATE")) if station else "",
                        "station_last_sample_date": parse_date(station.get("LAST SAMPLE DATE")) if station else "",
                    }
                    for column_index, column_name in enumerate(measurement_names, start=4):
                        value = values[column_index] if column_index < len(values) else None
                        if is_missing_sentinel(value):
                            sentinel_counts[column_name] += 1
                            combined_sentinels[column_name] += 1
                            row[column_name] = ""
                        else:
                            row[column_name] = csv_value(value)
                        if value is None or clean_text(value) == "":
                            dataset_counts[f"blank_{column_name}"] += 1
                    writer.writerow(row)

                repeated_keys = sum(1 for count in repeated_event_counts.values() if count > 1)
                dataset_report = {
                    "source_workbook": workbook_path.name,
                    "source_sheet": expected_sheet,
                    "row_count": dataset_counts["rows"],
                    "unique_point_ids": len(point_ids),
                    "matched_unique_point_ids": len(matched_point_ids),
                    "unmatched_unique_point_ids": len(unmatched_point_ids),
                    "ambiguous_unique_point_ids": len(ambiguous_point_ids),
                    "station_matched_rows": dataset_counts["station_matched_rows"],
                    "station_unmatched_rows": dataset_counts["station_unmatched_rows"],
                    "station_ambiguous_rows": dataset_counts["station_ambiguous_rows"],
                    "missing_point_id_rows": dataset_counts["missing_point_id_rows"],
                    "exact_duplicate_rows_after_first": dataset_counts["exact_duplicate_rows_after_first"],
                    "repeated_station_point_date_groups": repeated_keys,
                    "date_min": date_min.isoformat() if date_min else None,
                    "date_max": date_max.isoformat() if date_max else None,
                    "missing_date_rows": dataset_counts["missing_date_rows"],
                    "invalid_date_rows": dataset_counts["invalid_date_rows"],
                    "missing_sentinel_counts_by_measurement": dict(sentinel_counts),
                    "blank_counts_by_measurement": {
                        key.removeprefix("blank_"): value
                        for key, value in dataset_counts.items() if key.startswith("blank_")
                    },
                    "measurement_fields": measurement_metadata,
                }
                report["datasets"][kind] = dataset_report
                combined_counts["rows"] += dataset_counts["rows"]
                combined_counts["station_matched_rows"] += dataset_counts["station_matched_rows"]
                combined_counts["station_unmatched_rows"] += dataset_counts["station_unmatched_rows"]
                combined_counts["station_ambiguous_rows"] += dataset_counts["station_ambiguous_rows"]
            finally:
                workbook.close()

    report["combined"] = {
        "output_csv": str(output_path),
        "output_rows": combined_counts["rows"],
        "station_matched_rows": combined_counts["station_matched_rows"],
        "station_unmatched_rows": combined_counts["station_unmatched_rows"],
        "station_ambiguous_rows": combined_counts["station_ambiguous_rows"],
        "station_match_rate": combined_counts["station_matched_rows"] / combined_counts["rows"] if combined_counts["rows"] else None,
        "missing_sentinel_counts_by_measurement": dict(combined_sentinels),
        "output_sha256": sha256_file(output_path),
        "output_bytes": output_path.stat().st_size,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an auditable South African historical water-chemistry dataset.")
    parser.add_argument("--stations", required=True, help="WRO Sample stations.xlsx workbook")
    parser.add_argument("--rivers", required=True, help="WRO Rivers 1999-2012 workbook")
    parser.add_argument("--dams-lakes", required=True, help="WRO Dams and lakes 1999-2012 workbook")
    parser.add_argument("--output", default="data/processed/sa_historical_water_chemistry.csv")
    parser.add_argument("--report", default="artifacts/sa_historical_data_quality.json")
    args = parser.parse_args()
    try:
        report = build_dataset(
            Path(args.stations), Path(args.rivers), Path(args.dams_lakes),
            Path(args.output), Path(args.report),
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "combined": report["combined"],
        "datasets": {
            key: {
                "row_count": value["row_count"],
                "date_min": value["date_min"],
                "date_max": value["date_max"],
                "station_matched_rows": value["station_matched_rows"],
                "station_unmatched_rows": value["station_unmatched_rows"],
            }
            for key, value in report["datasets"].items()
        },
        "report": args.report,
        "warning": report["interpretation_warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
