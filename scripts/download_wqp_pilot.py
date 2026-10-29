"""Download a bounded Water Quality Portal Result-service pilot.

Requires an explicit site ID or state code and date interval. Raw CSV is retained;
this script does not merge different sample events or convert units.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ENDPOINT = "https://www.waterqualitydata.us/data/Result/search"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a bounded Water Quality Portal pilot dataset.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--siteid", help="Exact WQP site identifier, e.g. USGS-01594440.")
    scope.add_argument("--statecode", help="US state code, e.g. US:55; use a small pilot scope.")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD.")
    parser.add_argument("--characteristic", action="append", required=True,
                        help="Exact characteristic name; repeat to request more than one.")
    parser.add_argument("--output", default="data/environmental/wqp_results.csv")
    parser.add_argument("--max-records", type=int, default=100000)
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    if end < start:
        parser.error("--end-date must be on or after --start-date")
    if args.max_records < 1:
        parser.error("--max-records must be positive")

    params = {
        "startDateLo": start.isoformat(),
        "startDateHi": end.isoformat(),
        "characteristicName": args.characteristic,
        "mimeType": "csv",
        "zip": "no",
        "sorted": "no",
    }
    if args.siteid:
        params["siteid"] = args.siteid
    else:
        params["statecode"] = args.statecode

    response = requests.get(ENDPOINT, params=params, timeout=180,
                            headers={"User-Agent": "AquaSentinel-ML/0.1 (research data ingestion)"})
    response.raise_for_status()
    if not response.text.strip():
        raise RuntimeError("Water Quality Portal returned an empty response.")
    if len(response.content) > 250 * 1024 * 1024:
        raise RuntimeError("Response exceeds the 250 MiB safety limit; narrow the query.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)

    # Count parsed data rows without changing or rewriting the source CSV.
    import csv
    with output.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        row_count = sum(1 for _ in reader)
    if row_count > args.max_records:
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"Query returned {row_count:,} records, above --max-records={args.max_records:,}. "
            "Narrow the site, date interval, or characteristic list and retry."
        )

    metadata = {
        "source": "https://www.waterqualitydata.us/",
        "service_endpoint": ENDPOINT,
        "request_url": response.url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "query": {
            "siteid": args.siteid,
            "statecode": args.statecode,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "characteristics": args.characteristic,
        },
        "row_count": row_count,
        "column_names": header,
        "sha256": sha256_file(output),
        "local_file": str(output),
        "interpretation_warning": (
            "These are discrete sample results, not necessarily continuous time-series data. "
            "Preserve site, activity, date, characteristic, result unit, method, fraction, and "
            "detection-limit fields. Do not compare unlike units/methods or treat an anomaly as "
            "proof of contamination or a health risk."
        ),
    }
    metadata_path = output.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {row_count:,} result rows and {len(header)} columns.")
    print(f"Raw CSV: {output}")
    print(f"Query metadata: {metadata_path}")


if __name__ == "__main__":
    main()
