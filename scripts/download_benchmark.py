"""Download and audit the public AquaSentinel benchmark CSV.

The downloaded benchmark is kept separate from environmental observations.
The source revision and SHA-256 are recorded for reproducibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO_ID = "kheejay88/water_potability"
FILE_NAME = "water_potability.csv"
FEATURES = [
    "ph", "Hardness", "Solids", "Chloramines", "Sulfate",
    "Conductivity", "Organic_carbon", "Trihalomethanes", "Turbidity",
]
TARGET_CANDIDATES = ("Potability", "potability", "target", "label")
API_URL = f"https://huggingface.co/api/datasets/{REPO_ID}/revision/main"
DOWNLOAD_URL = f"https://huggingface.co/datasets/{REPO_ID}/resolve/{{revision}}/{FILE_NAME}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and audit the public water-potability benchmark.")
    parser.add_argument("--output", default="data/benchmark/water_potability.csv")
    parser.add_argument("--audit", default="artifacts/benchmark_audit.json")
    args = parser.parse_args()

    output = Path(args.output)
    audit_path = Path(args.audit)
    output.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(API_URL, timeout=60)
    response.raise_for_status()
    metadata = response.json()
    revision = metadata.get("sha")
    if not revision:
        raise RuntimeError("Hugging Face API response did not include a dataset revision SHA.")

    download = requests.get(DOWNLOAD_URL.format(revision=revision), timeout=120)
    download.raise_for_status()
    output.write_bytes(download.content)

    frame = pd.read_csv(output)
    target = next((name for name in TARGET_CANDIDATES if name in frame.columns), None)
    missing_features = [name for name in FEATURES if name not in frame.columns]
    if target is None:
        raise ValueError(f"No binary target found. Available columns: {list(frame.columns)}")
    if missing_features:
        raise ValueError(f"Missing expected feature columns: {missing_features}")

    numeric = frame[FEATURES].apply(pd.to_numeric, errors="coerce")
    labels = pd.to_numeric(frame[target], errors="coerce")
    audit = {
        "source": f"https://huggingface.co/datasets/{REPO_ID}",
        "file": FILE_NAME,
        "revision": revision,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "license_metadata": metadata.get("cardData", {}).get("license"),
        "row_count": int(len(frame)),
        "column_names": list(frame.columns),
        "target_column": target,
        "target_values": {str(k): int(v) for k, v in labels.value_counts(dropna=False).items()},
        "target_invalid_or_missing": int(labels.isna().sum() + (~labels.dropna().isin([0, 1])).sum()),
        "feature_missing_counts": {k: int(v) for k, v in numeric.isna().sum().items()},
        "duplicate_rows": int(frame.duplicated().sum()),
        "feature_descriptive_statistics": numeric.describe().replace({float("nan"): None}).to_dict(),
        "sha256": sha256_file(output),
        "local_file": str(output),
        "provenance_warning": (
            "The dataset card contains minimal provenance information. The binary label is a benchmark "
            "target, not verified evidence of compliance with a current drinking-water standard."
        ),
    }
    audit_path.write_text(json.dumps(audit, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Downloaded {len(frame):,} rows at revision {revision}.")
    print(f"CSV: {output}")
    print(f"Audit: {audit_path}")
    print("Review the audit and dataset provenance before modelling.")


if __name__ == "__main__":
    main()
