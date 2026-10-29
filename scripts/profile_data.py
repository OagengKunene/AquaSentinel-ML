"""Exploratory audit for either AquaSentinel research data track.

This is descriptive analysis only. It does not merge sample events, harmonise
units, infer regulatory compliance, or train an anomaly detector.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from aquasentinel.features import FEATURES


def profile_csv(path: str, target: str | None = None) -> dict:
    frame = pd.read_csv(path, low_memory=False)
    if frame.empty:
        raise ValueError("Input CSV is empty.")

    numeric = frame.select_dtypes(include="number")
    missing = frame.isna().sum()
    duplicate_count = int(frame.duplicated().sum())
    result = {
        "file": str(path),
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "column_names": list(frame.columns),
        "duplicate_rows": duplicate_count,
        "missing_counts": {str(k): int(v) for k, v in missing.items()},
        "missing_percent": {
            str(k): round(float(v) * 100 / len(frame), 3)
            for k, v in missing.items()
        },
        "numeric_summary": numeric.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99])
            .replace({float("nan"): None}).to_dict(),
        "numeric_correlation": numeric.corr(min_periods=3)
            .replace({float("nan"): None}).to_dict(),
    }

    available_features = [feature for feature in FEATURES if feature in frame.columns]
    result["expected_benchmark_features_present"] = available_features
    result["expected_benchmark_features_missing"] = [
        feature for feature in FEATURES if feature not in frame.columns
    ]
    if target:
        if target not in frame.columns:
            raise ValueError(f"Target column '{target}' not found.")
        labels = frame[target].value_counts(dropna=False)
        result["target_column"] = target
        result["target_distribution"] = {
            str(k): int(v) for k, v in labels.items()
        }
        if len(available_features) == len(FEATURES):
            grouped = frame.groupby(target)[FEATURES].median(numeric_only=True)
            result["feature_medians_by_target"] = grouped.replace(
                {float("nan"): None}
            ).to_dict()

    # WQP files usually contain long-form result records. These summaries help
    # identify heterogeneity without incorrectly pivoting unrelated samples.
    for column in ("CharacteristicName", "ResultMeasure/MeasureUnitCode",
                   "ResultMeasure.MeasureUnitCode", "ProviderName", "OrganizationIdentifier"):
        if column in frame.columns:
            result[f"top_values_{column}"] = {
                str(k): int(v) for k, v in frame[column].value_counts(dropna=False).head(20).items()
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a descriptive data-quality report.")
    parser.add_argument("--data", required=True, help="Input CSV from Track A or Track B.")
    parser.add_argument("--target", help="Optional binary target column (normally Track A only).")
    parser.add_argument("--output", default="artifacts/data_profile.json")
    args = parser.parse_args()

    report = profile_csv(args.data, args.target)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Profile written to {destination}")
    print(f"Rows: {report['rows']:,}; columns: {report['columns']}; duplicates: {report['duplicate_rows']:,}")


if __name__ == "__main__":
    main()
