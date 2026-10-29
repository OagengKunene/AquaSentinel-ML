"""Audit and explicitly normalize South African DWS/RQIS CSV exports.

The DWS export schema is not assumed. First run in audit-only mode, inspect
exact headers, then provide a JSON mapping. Original raw files are never edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

MAX_INPUT_BYTES = 250 * 1024 * 1024
REQUIRED_MAPPING_KEYS = (
    "station_id", "sample_datetime", "parameter_name", "result_value", "result_unit"
)
OPTIONAL_MAPPING_KEYS = (
    "sample_id", "method", "fraction", "detection_limit", "qualifier", "provider"
)
ALIASES = {
    "station_id": ("station", "stationid", "monitoringpoint", "monitoringpointcode",
                   "siteid", "sitecode", "monitoringsite", "locationid"),
    "sample_datetime": ("sampledate", "samplingdate", "sampledatetime", "activitystartdate",
                        "date", "collectiondate", "samplingdatetime"),
    "parameter_name": ("parameter", "determinant", "determinantname", "characteristic",
                       "characteristicname", "variable", "constituent"),
    "result_value": ("result", "resultvalue", "resultmeasurevalue", "value", "measurement",
                     "measurementvalue", "concentration"),
    "result_unit": ("unit", "units", "resultunit", "resultmeasureunitcode",
                    "resultmeasuremeasureunitcode", "measurementunit"),
    "sample_id": ("sampleid", "sampleidentifier", "activityid", "activityidentifier",
                  "eventid", "sampleeventid"),
    "method": ("method", "methodname", "analyticalmethod", "methodidentifier"),
    "fraction": ("fraction", "fractionname", "resultfractiontext"),
    "detection_limit": ("detectionlimit", "detectionlimitvalue", "quantitationlimit",
                        "quantitationlimitvalue"),
    "qualifier": ("qualifier", "resultqualifier", "resultcomment"),
    "provider": ("provider", "organization", "organizationname", "laboratory"),
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def suggest_columns(columns: list[str]) -> dict[str, list[str]]:
    normalized = {normalize_header(column): column for column in columns}
    suggestions = {}
    for canonical, aliases in ALIASES.items():
        matches = [normalized[alias] for alias in aliases if alias in normalized]
        suggestions[canonical] = matches
    return suggestions


def load_mapping(path: Path, columns: list[str]) -> dict[str, str]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("Mapping JSON must be an object of canonical-field to exact CSV-header pairs.")
    unknown_keys = set(mapping) - set(REQUIRED_MAPPING_KEYS) - set(OPTIONAL_MAPPING_KEYS)
    if unknown_keys:
        raise ValueError(f"Unknown mapping keys: {sorted(unknown_keys)}")
    missing = [key for key in REQUIRED_MAPPING_KEYS if not mapping.get(key)]
    if missing:
        raise ValueError(f"Mapping is missing required fields: {missing}")
    invalid = {key: value for key, value in mapping.items()
               if value and value not in columns}
    if invalid:
        raise ValueError(f"Mapped CSV headers do not exist (match exact spelling): {invalid}")
    return {key: value for key, value in mapping.items() if value}


def audit_dws_csv(input_path: Path, mapping_path: Path | None = None,
                  output_path: Path | None = None, source_url: str | None = None,
                  dataset_name: str = "DWS/RQIS user-supplied export") -> dict:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    payload = input_path.read_bytes()
    if not payload:
        raise ValueError("Input CSV is empty.")
    if len(payload) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds the 250 MiB limit; split the export into smaller files.")
    try:
        frame = pd.read_csv(
            input_path, dtype=str, keep_default_na=False, encoding="utf-8-sig",
            sep=None, engine="python",
        )
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not parse the source as a UTF-8 CSV: {exc}") from exc
    if frame.empty or len(frame.columns) == 0:
        raise ValueError("CSV contains no data rows or no columns.")
    columns = [str(column) for column in frame.columns]
    metadata = {
        "source_owner": "South African Department of Water and Sanitation (DWS)",
        "source_programme": dataset_name,
        "source_url": source_url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file_name": input_path.name,
        "source_file_sha256": sha256_bytes(payload),
        "source_file_bytes": len(payload),
        "row_count": int(len(frame)),
        "column_count": int(len(columns)),
        "column_names": columns,
        "suggested_mapping_only_review_required": suggest_columns(columns),
        "duplicate_raw_rows": int(frame.duplicated().sum()),
        "blank_counts": {
            column: int(frame[column].astype(str).str.strip().eq("").sum())
            for column in columns
        },
        "mapping_applied": None,
        "normalized_output": None,
        "interpretation_warning": (
            "This is a schema and data-quality audit, not a regulatory assessment. "
            "DWS/RQIS exports may be historical snapshots. Preserve station and sample-event "
            "identifiers, parameter names, units, methods, fractions, qualifiers and detection "
            "limits. Do not compare unlike methods or units or interpret statistical outliers "
            "as proof of contamination, unsafe water, health risk or regulatory exceedance."
        ),
    }

    if mapping_path:
        mapping = load_mapping(mapping_path, columns)
        normalized = pd.DataFrame(index=frame.index)
        for key in REQUIRED_MAPPING_KEYS + OPTIONAL_MAPPING_KEYS:
            source_column = mapping.get(key)
            normalized[key] = frame[source_column] if source_column else ""
        normalized["result_value_numeric"] = pd.to_numeric(
            normalized["result_value"].str.strip().replace("", pd.NA),
            errors="coerce",
        )
        parsed_dates = pd.to_datetime(
            normalized["sample_datetime"].replace("", pd.NA),
            errors="coerce", utc=True,
        )
        normalized["sample_datetime_utc"] = parsed_dates
        normalized["normalization_status"] = "ready_for_review"
        normalized.loc[normalized["station_id"].str.strip().eq(""), "normalization_status"] = "missing_station_id"
        normalized.loc[normalized["parameter_name"].str.strip().eq(""), "normalization_status"] = "missing_parameter_name"
        normalized.loc[normalized["result_unit"].str.strip().eq(""), "normalization_status"] = "missing_result_unit"
        normalized.loc[normalized["result_value_numeric"].isna(), "normalization_status"] = "invalid_or_missing_numeric_result"
        normalized.loc[parsed_dates.isna(), "normalization_status"] = "invalid_or_missing_sample_datetime"

        # Retain every original field for traceability; no source field is discarded.
        for column in columns:
            normalized[f"raw__{column}"] = frame[column]
        normalized["source_file_name"] = input_path.name
        normalized["source_file_sha256"] = metadata["source_file_sha256"]
        normalized["source_url"] = source_url or ""
        normalized["source_dataset"] = dataset_name
        normalized["source_row_number"] = range(2, len(frame) + 2)

        if output_path is None:
            output_path = input_path.with_name(input_path.stem + ".normalized.csv")
        if output_path.resolve() == input_path.resolve():
            raise ValueError("Normalized output must not overwrite the original raw source file.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(output_path, index=False)
        metadata["mapping_applied"] = mapping
        metadata["normalized_output"] = str(output_path)
        metadata["normalization_status_counts"] = {
            str(key): int(value)
            for key, value in normalized["normalization_status"].value_counts(dropna=False).items()
        }
        valid_dates = parsed_dates.dropna()
        metadata["parsed_sample_datetime_min_utc"] = (
            valid_dates.min().isoformat() if not valid_dates.empty else None
        )
        metadata["parsed_sample_datetime_max_utc"] = (
            valid_dates.max().isoformat() if not valid_dates.empty else None
        )
        metadata["unit_values_by_parameter"] = {
            str(parameter): sorted(group["result_unit"].dropna().astype(str).unique().tolist())
            for parameter, group in normalized.groupby("parameter_name", dropna=False)
        }

    report_path = input_path.with_suffix(input_path.suffix + ".audit.json")
    metadata["audit_report"] = str(report_path)
    report_path.write_text(json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit a DWS/RQIS CSV first; optionally normalize using an explicit exact-header mapping."
    )
    parser.add_argument("--input", required=True, help="Original DWS/RQIS CSV export.")
    parser.add_argument("--mapping", help="JSON mapping from canonical field names to exact source headers.")
    parser.add_argument("--output", help="Normalized CSV destination; only used with --mapping.")
    parser.add_argument("--source-url", help="URL or data-request reference supplied with the extract.")
    parser.add_argument("--dataset-name", default="DWS/RQIS user-supplied export")
    args = parser.parse_args()
    try:
        result = audit_dws_csv(
            Path(args.input), Path(args.mapping) if args.mapping else None,
            Path(args.output) if args.output else None, args.source_url, args.dataset_name,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "rows": result["row_count"],
        "columns": result["column_count"],
        "sha256": result["source_file_sha256"],
        "audit_report": result["audit_report"],
        "normalized_output": result["normalized_output"],
        "mapping_suggestions": result["suggested_mapping_only_review_required"],
        "normalization_status_counts": result.get("normalization_status_counts"),
        "warning": result["interpretation_warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
