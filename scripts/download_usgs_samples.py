"""Download bounded discrete water-quality results from the modern USGS Samples API.

Raw CSV is retained unchanged. This adapter does not harmonise units, infer
sample events, or convert statistical flags into safety conclusions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ENDPOINT = "https://api.waterdata.usgs.gov/samples-data/results/narrow"
MAX_RESPONSE_BYTES = 250 * 1024 * 1024


def build_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "AquaSentinel-ML/0.2 (research data ingestion)"})
    return session


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_query(site_id: str, start_date: date, end_date: date,
                characteristic: str | None = None,
                usgs_parameter_code: str | None = None) -> dict[str, str]:
    if not site_id.startswith("USGS-") or len(site_id) <= 5:
        raise ValueError("site_id must be a USGS identifier such as USGS-04024315")
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if not characteristic and not usgs_parameter_code:
        raise ValueError("Specify --characteristic or --usgs-pcode to keep the query bounded")
    params = {
        "mimeType": "text/csv",
        "monitoringLocationIdentifier": site_id,
        "activityStartDateLower": start_date.isoformat(),
        "activityStartDateUpper": end_date.isoformat(),
    }
    if characteristic:
        params["characteristic"] = characteristic
    if usgs_parameter_code:
        params["usgsPCode"] = usgs_parameter_code
    return params


def parse_csv_payload(content: bytes, max_records: int) -> tuple[list[str], int]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("USGS response was not UTF-8 CSV") from exc
    reader = csv.reader(text.splitlines())
    header = next(reader, [])
    if not header or len(header) < 2:
        raise ValueError("USGS response did not contain a recognisable CSV header")
    if any("html" in cell.lower() or "error" == cell.lower() for cell in header):
        raise ValueError("USGS returned an error document instead of CSV")
    rows = sum(1 for _ in reader)
    if rows > max_records:
        raise ValueError(
            f"Query returned {rows:,} records, above --max-records={max_records:,}; narrow the query"
        )
    return header, rows


def download(site_id: str, start_date: date, end_date: date,
             characteristic: str | None, usgs_parameter_code: str | None,
             output: Path, max_records: int = 100000,
             session: requests.Session | None = None) -> dict:
    if max_records < 1:
        raise ValueError("max_records must be positive")
    params = build_query(site_id, start_date, end_date, characteristic, usgs_parameter_code)
    client = session or build_session()
    response = client.get(ENDPOINT, params=params, timeout=(15, 180))
    response.raise_for_status()
    if not response.content:
        raise ValueError("USGS returned an empty response")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("USGS response exceeds the 250 MiB safety limit; narrow the query")
    header, row_count = parse_csv_payload(response.content, max_records)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_bytes(response.content)
    temporary.replace(output)

    metadata = {
        "source": "United States Geological Survey (USGS) Water Data for the Nation",
        "service": "USGS Samples API",
        "endpoint": ENDPOINT,
        "request_url": response.url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "query": {
            "monitoring_location_identifier": site_id,
            "activity_start_date_lower": start_date.isoformat(),
            "activity_start_date_upper": end_date.isoformat(),
            "characteristic": characteristic,
            "usgs_parameter_code": usgs_parameter_code,
            "profile": "narrow",
        },
        "row_count": row_count,
        "column_names": header,
        "sha256": sha256_bytes(response.content),
        "local_file": str(output),
        "interpretation_warning": (
            "Discrete sample results are not continuous sensor readings. Preserve activity/sample "
            "identifiers, dates, characteristic, result value and unit, method, fraction, qualifiers, "
            "detection/quantitation limits and provider metadata. Do not compare unlike methods or "
            "units, and do not interpret statistical anomalies as proof of contamination, unsafe "
            "water, health risk or regulatory exceedance."
        ),
    }
    metadata_path = output.with_suffix(output.suffix + ".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a bounded site/date/parameter selection from the USGS Samples API."
    )
    parser.add_argument("--site-id", required=True, help="USGS site ID, e.g. USGS-04024315")
    parser.add_argument("--start-date", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--characteristic", help="Characteristic name, e.g. pH")
    parser.add_argument("--usgs-pcode", help="USGS parameter code")
    parser.add_argument("--output", default="data/environmental/usgs_samples.csv")
    parser.add_argument("--max-records", type=int, default=100000)
    args = parser.parse_args()
    try:
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
        metadata = download(
            args.site_id, start, end, args.characteristic, args.usgs_pcode,
            Path(args.output), args.max_records,
        )
    except (ValueError, requests.RequestException) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "row_count": metadata["row_count"],
        "columns": len(metadata["column_names"]),
        "raw_csv": metadata["local_file"],
        "metadata": str(Path(metadata["local_file"]).with_suffix(Path(metadata["local_file"]).suffix + ".metadata.json")),
        "sha256": metadata["sha256"],
        "request_url": metadata["request_url"],
    }, indent=2))


if __name__ == "__main__":
    main()
