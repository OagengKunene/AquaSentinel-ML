"""Parameter-aware anomaly screening for Water Quality Portal result CSVs.

This is an exploratory ranking tool, not a contamination detector. It does not
harmonise units, combine sample events, or make regulatory/health conclusions.
By default, each parameter-unit combination is analysed separately per site.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

VALUE_CANDIDATES = ("ResultMeasureValue", "ResultMeasure.MeasureValue")
UNIT_CANDIDATES = (
    "ResultMeasure/MeasureUnitCode",
    "ResultMeasure.MeasureUnitCode",
    "ResultMeasureUnitCode",
)
SITE_CANDIDATES = ("MonitoringLocationIdentifier", "MonitoringLocationID", "siteid")
PARAMETER_CANDIDATES = ("CharacteristicName", "Characteristic")
SAMPLE_CANDIDATES = ("ActivityIdentifier", "ActivityID")
DATE_CANDIDATES = ("ActivityStartDate", "ActivityStartDateTime")


def first_column(frame: pd.DataFrame, candidates: tuple[str, ...], required: bool = True):
    found = next((column for column in candidates if column in frame.columns), None)
    if required and found is None:
        raise ValueError(f"Required WQP column not found. Expected one of: {candidates}")
    return found


def robust_z_scores(values: pd.Series) -> np.ndarray:
    array = values.to_numpy(dtype=float)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    if mad == 0:
        # A zero MAD means the robust scale is undefined. Do not manufacture
        # infinite scores; use NaN so this method abstains for the group.
        return np.full(array.shape, np.nan, dtype=float)
    return 0.6744897501960817 * (array - median) / mad


def screen_group(values: pd.Series, seed: int, contamination: float,
                 min_samples: int) -> dict:
    clean = pd.to_numeric(values, errors="coerce")
    valid = clean.notna() & np.isfinite(clean)
    x = clean.loc[valid].to_numpy(dtype=float)
    output = {
        "n_valid": int(len(x)),
        "robust_z": np.full(len(values), np.nan),
        "robust_flag": np.zeros(len(values), dtype=bool),
        "iforest_score": np.full(len(values), np.nan),
        "iforest_flag": np.zeros(len(values), dtype=bool),
        "lof_score": np.full(len(values), np.nan),
        "lof_flag": np.zeros(len(values), dtype=bool),
        "status": "screened",
    }
    if len(x) < min_samples:
        output["status"] = f"skipped_too_few_records<{min_samples}"
        return output

    positions = np.flatnonzero(valid.to_numpy())
    z = robust_z_scores(pd.Series(x))
    output["robust_z"][positions] = z
    output["robust_flag"][positions] = np.isfinite(z) & (np.abs(z) >= 3.5)

    matrix = x.reshape(-1, 1)
    forest = IsolationForest(
        n_estimators=250, contamination=contamination,
        random_state=seed, n_jobs=-1,
    )
    forest.fit(matrix)
    output["iforest_score"][positions] = -forest.score_samples(matrix)
    output["iforest_flag"][positions] = forest.predict(matrix) == -1

    neighbours = min(20, len(x) - 1)
    lof = LocalOutlierFactor(n_neighbors=neighbours, contamination=contamination)
    lof_labels = lof.fit_predict(matrix)
    output["lof_score"][positions] = -lof.negative_outlier_factor_
    output["lof_flag"][positions] = lof_labels == -1
    return output


def analyse(frame: pd.DataFrame, scope: str = "site", min_samples: int = 30,
            contamination: float = 0.02, seed: int = 42):
    value_col = first_column(frame, VALUE_CANDIDATES)
    unit_col = first_column(frame, UNIT_CANDIDATES)
    site_col = first_column(frame, SITE_CANDIDATES, required=False)
    parameter_col = first_column(frame, PARAMETER_CANDIDATES, required=False)
    if parameter_col is None:
        raise ValueError("Characteristic/parameter column is required.")
    if scope == "site" and site_col is None:
        raise ValueError("Site-scoped screening requested but no site identifier column exists.")

    result = frame.copy()
    numeric = pd.to_numeric(result[value_col], errors="coerce")
    result["_aqua_numeric_value"] = numeric
    keys = [parameter_col, unit_col]
    if scope == "site":
        keys.append(site_col)
    groupby_arg = keys[0] if len(keys) == 1 else keys
    grouped = result.groupby(groupby_arg, dropna=False, sort=False).groups

    for suffix, dtype in (
        ("robust_z", float), ("robust_flag", bool),
        ("iforest_score", float), ("iforest_flag", bool),
        ("lof_score", float), ("lof_flag", bool),
    ):
        result[f"aqua_{suffix}"] = np.nan if dtype is float else False
    result["aqua_group_status"] = "not_screened"

    summaries = []
    for group_key, indexes in grouped.items():
        group_values = result.loc[indexes, value_col]
        screened = screen_group(group_values, seed, contamination, min_samples)
        for suffix in ("robust_z", "robust_flag", "iforest_score",
                       "iforest_flag", "lof_score", "lof_flag"):
            result.loc[indexes, f"aqua_{suffix}"] = screened[suffix]
        result.loc[indexes, "aqua_group_status"] = screened["status"]
        summary = {
            "group": group_key if isinstance(group_key, tuple) else (group_key,),
            "n_records": int(len(indexes)),
            "n_valid": screened["n_valid"],
            "status": screened["status"],
            "robust_flag_count": int(np.sum(screened["robust_flag"])),
            "iforest_flag_count": int(np.sum(screened["iforest_flag"])),
            "lof_flag_count": int(np.sum(screened["lof_flag"])),
        }
        summaries.append(summary)

    report = {
        "methodology": {
            "scope": scope,
            "grouping_columns": keys,
            "min_samples_per_group": min_samples,
            "isolation_forest_contamination": contamination,
            "robust_z_threshold": 3.5,
            "methods": ["median/MAD robust z-score", "Isolation Forest", "Local Outlier Factor"],
            "warning": (
                "Anomaly flags are statistical screening signals only. They do not establish "
                "contamination, a health risk, or regulatory non-compliance. Results depend on "
                "site/parameter scope, sampling design, method, censoring and data quality."
            ),
        },
        "input_rows": int(len(frame)),
        "groups": summaries,
        "groups_screened": int(sum(item["status"] == "screened" for item in summaries)),
        "groups_skipped": int(sum(item["status"] != "screened" for item in summaries)),
    }
    return result, report


def main():
    parser = argparse.ArgumentParser(description="Screen WQP measurements for unusual values.")
    parser.add_argument("--data", required=True, help="Raw WQP result CSV.")
    parser.add_argument("--output", default="artifacts/wqp_anomaly_screened.csv")
    parser.add_argument("--report", default="artifacts/wqp_anomaly_report.json")
    parser.add_argument("--scope", choices=("site", "parameter"), default="site",
                        help="site keeps each site separate; parameter pools sites only within identical parameter/unit.")
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--contamination", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.min_samples < 10:
        parser.error("--min-samples must be at least 10")
    if not 0.001 <= args.contamination <= 0.2:
        parser.error("--contamination must be between 0.001 and 0.2")

    frame = pd.read_csv(args.data, low_memory=False)
    if frame.empty:
        parser.error("Input dataset is empty.")
    screened, report = analyse(
        frame, scope=args.scope, min_samples=args.min_samples,
        contamination=args.contamination, seed=args.seed,
    )
    output, report_path = Path(args.output), Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    screened.to_csv(output, index=False)
    report["output_csv"] = str(output)
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "groups_screened": report["groups_screened"],
        "groups_skipped": report["groups_skipped"],
        "output": str(output),
        "report": str(report_path),
        "warning": report["methodology"]["warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
