"""Causal, site-aware temporal anomaly screening for discrete WQP observations.

Each timestamp is compared only with earlier observations from the same
site/parameter/unit group. Same-timestamp rows are scored together before
being added to history. This is a statistical screening aid, not a safety test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.anomaly_screen import (
    PARAMETER_CANDIDATES, SITE_CANDIDATES, UNIT_CANDIDATES, VALUE_CANDIDATES,
    first_column,
)
from scripts.anomaly_screen import DATE_CANDIDATES


def temporal_screen(
    frame: pd.DataFrame,
    min_history: int = 20,
    lookback: int = 60,
    threshold: float = 3.5,
):
    if min_history < 3:
        raise ValueError("min_history must be at least 3")
    if lookback < min_history:
        raise ValueError("lookback must be greater than or equal to min_history")
    if threshold <= 0:
        raise ValueError("threshold must be positive")

    value_col = first_column(frame, VALUE_CANDIDATES)
    unit_col = first_column(frame, UNIT_CANDIDATES)
    site_col = first_column(frame, SITE_CANDIDATES)
    parameter_col = first_column(frame, PARAMETER_CANDIDATES)
    date_col = first_column(frame, DATE_CANDIDATES)

    result = frame.copy().reset_index(drop=True)
    values = pd.to_numeric(result[value_col], errors="coerce")
    timestamps = pd.to_datetime(result[date_col], errors="coerce", utc=True)

    result["aqua_temporal_robust_z"] = np.nan
    result["aqua_temporal_flag"] = False
    result["aqua_temporal_history_count"] = 0
    result["aqua_temporal_status"] = "not_evaluated"

    grouping = [site_col, parameter_col, unit_col]
    grouped = result.groupby(grouping, dropna=False, sort=False).groups
    flagged = 0
    evaluated = 0
    insufficient = 0
    invalid_time = int(timestamps.isna().sum())

    for _, indexes in grouped.items():
        valid_indexes = [
            int(i) for i in indexes
            if pd.notna(timestamps.iloc[int(i)]) and
            pd.notna(values.iloc[int(i)]) and
            np.isfinite(float(values.iloc[int(i)]))
        ]
        invalid_indexes = [int(i) for i in indexes if int(i) not in set(valid_indexes)]
        for i in invalid_indexes:
            if pd.isna(timestamps.iloc[i]):
                result.at[i, "aqua_temporal_status"] = "missing_or_invalid_timestamp"
            else:
                result.at[i, "aqua_temporal_status"] = "missing_or_invalid_measurement"

        valid_indexes.sort(key=lambda i: timestamps.iloc[i])
        history: list[float] = []
        cursor = 0
        while cursor < len(valid_indexes):
            current_time = timestamps.iloc[valid_indexes[cursor]]
            batch = []
            while cursor < len(valid_indexes) and timestamps.iloc[valid_indexes[cursor]] == current_time:
                batch.append(valid_indexes[cursor])
                cursor += 1

            baseline = history[-lookback:]
            for i in batch:
                result.at[i, "aqua_temporal_history_count"] = len(baseline)
                if len(baseline) < min_history:
                    result.at[i, "aqua_temporal_status"] = "insufficient_prior_history"
                    insufficient += 1
                    continue

                baseline_array = np.asarray(baseline, dtype=float)
                median = float(np.median(baseline_array))
                mad = float(np.median(np.abs(baseline_array - median)))
                if mad == 0:
                    result.at[i, "aqua_temporal_status"] = "zero_mad_abstained"
                    continue

                score = 0.6744897501960817 * (float(values.iloc[i]) - median) / mad
                is_flagged = abs(score) >= threshold
                result.at[i, "aqua_temporal_robust_z"] = score
                result.at[i, "aqua_temporal_flag"] = is_flagged
                result.at[i, "aqua_temporal_status"] = "flagged" if is_flagged else "screened"
                evaluated += 1
                flagged += int(is_flagged)

            # Do not let observations at the same timestamp influence one another.
            history.extend(float(values.iloc[i]) for i in batch)

    report = {
        "method": "causal rolling median/MAD robust z-score",
        "grouping_columns": grouping,
        "timestamp_column": date_col,
        "minimum_prior_observations": min_history,
        "maximum_prior_observations": lookback,
        "absolute_robust_z_threshold": threshold,
        "input_rows": int(len(result)),
        "evaluated_rows": evaluated,
        "flagged_rows": flagged,
        "insufficient_history_rows": insufficient,
        "invalid_timestamp_rows": invalid_time,
        "warning": (
            "Flags indicate unusual values relative to earlier observations at the same "
            "site for the same parameter and unit. They do not establish contamination, "
            "unsafe water, health risk or regulatory exceedance. Seasonal cycles, method "
            "changes, censoring, sampling frequency and site operations may affect results."
        ),
    }
    return result, report


def main():
    parser = argparse.ArgumentParser(description="Screen discrete water observations for temporal outliers.")
    parser.add_argument("--data", required=True, help="Raw WQP result CSV.")
    parser.add_argument("--output", default="artifacts/wqp_temporal_screened.csv")
    parser.add_argument("--report", default="artifacts/wqp_temporal_report.json")
    parser.add_argument("--min-history", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=60)
    parser.add_argument("--threshold", type=float, default=3.5)
    args = parser.parse_args()
    if args.min_history < 3:
        parser.error("--min-history must be at least 3")
    if args.lookback < args.min_history:
        parser.error("--lookback must be >= --min-history")
    if args.threshold <= 0:
        parser.error("--threshold must be positive")

    frame = pd.read_csv(args.data, low_memory=False)
    if frame.empty:
        parser.error("Input dataset is empty.")
    screened, report = temporal_screen(
        frame, min_history=args.min_history,
        lookback=args.lookback, threshold=args.threshold,
    )
    output, report_path = Path(args.output), Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    screened.to_csv(output, index=False)
    report["output_csv"] = str(output)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "input_rows": report["input_rows"],
        "evaluated_rows": report["evaluated_rows"],
        "flagged_rows": report["flagged_rows"],
        "insufficient_history_rows": report["insufficient_history_rows"],
        "output": str(output),
        "report": str(report_path),
        "warning": report["warning"],
    }, indent=2))


if __name__ == "__main__":
    main()
