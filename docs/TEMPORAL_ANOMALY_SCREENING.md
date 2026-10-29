# Temporal anomaly screening

## Why a separate temporal method?

Water Quality Portal records are commonly discrete sample results, not regularly sampled sensor streams. A temporal baseline is therefore built from the ordered observations available at one monitoring site, not by assuming evenly spaced time-series measurements.

## Method

`scripts/temporal_anomaly.py` compares each measurement with earlier observations from the same:

- monitoring site;
- characteristic/parameter;
- reported unit.

It uses a rolling median and median absolute deviation (MAD). By default it requires 20 prior valid observations, uses at most the most recent 60 prior observations, and flags absolute robust z-scores of 3.5 or greater.

Important safeguards:

- The current measurement is never included in its own reference baseline.
- Rows sharing the same timestamp are scored against the same prior history before any of them are added to that history.
- Sites, parameters and units are never pooled.
- Insufficient history is marked explicitly.
- If MAD is zero, the method abstains rather than inventing an infinite score.
- Missing timestamps and invalid measurements are retained and marked.

## Run

After downloading a WQP result CSV:

```bash
python -m scripts.temporal_anomaly --data data/environmental/wqp_results.csv
```

Optional settings:

```bash
python -m scripts.temporal_anomaly \
  --data data/environmental/wqp_results.csv \
  --min-history 20 \
  --lookback 60 \
  --threshold 3.5 \
  --output artifacts/wqp_temporal_screened.csv \
  --report artifacts/wqp_temporal_report.json
```

Output columns include `aqua_temporal_robust_z`, `aqua_temporal_flag`, `aqua_temporal_history_count` and `aqua_temporal_status`. A JSON report records the configuration and counts.

## Limitations

This initial baseline is causal and site-specific, but it is not a seasonal forecasting model. It does not account for irregular sampling intervals, annual/seasonal cycles, changes in analytical method, detection-limit censoring, sampling frequency, or operational events. An apparent change can be legitimate seasonality or a change in sampling practice. Review raw records and metadata, and validate any concern with qualified environmental professionals and appropriate laboratory/regulatory evidence.

An anomaly flag is not proof of contamination, unsafe drinking water, health risk or regulatory non-compliance. The tool is for research triage only.
