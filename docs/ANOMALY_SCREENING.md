# Environmental anomaly screening

## Purpose

`scripts/anomaly_screen.py` provides a first, cautious unsupervised screening pass over Water Quality Portal (WQP) result records. It adds three independent statistical flags to the input rows:

1. **Median/MAD robust z-score:** flags absolute robust z-scores at or above 3.5. If the median absolute deviation is zero, the method abstains for that group rather than producing infinite scores.
2. **Isolation Forest:** ranks unusual one-dimensional measurement values within the selected group.
3. **Local Outlier Factor (LOF):** identifies locally unusual values within the same one-dimensional group.

The CSV output retains original WQP columns and appends screening fields. A JSON report records group sizes and skipped groups.

## Run it

```bash
python -m scripts.anomaly_screen \
  --data data/environmental/wqp_results.csv \
  --scope site \
  --min-samples 30
```

Outputs:
- `artifacts/wqp_anomaly_screened.csv`
- `artifacts/wqp_anomaly_report.json`

### Grouping scope

- `--scope site` (default): separate groups by characteristic, reported unit, and monitoring site. This reduces the risk of comparing naturally different sites.
- `--scope parameter`: pools sites only within the same characteristic and reported unit. Use only when a cross-site reference distribution is scientifically appropriate.

Groups below `--min-samples` are skipped and marked; the script does not silently fit unstable detectors to tiny groups. Results are not converted between units. Detection-limit/censored records and method/fraction differences still require expert review before interpreting scores.

## Interpretation

An anomaly flag means only that a measurement is unusual relative to the observations in its chosen group and dataset. It does **not** establish contamination, unsafe drinking water, a health risk, or regulatory non-compliance. A flagged value may reflect a transcription error, a unit/method difference, a legitimate local event, seasonality, a change in sampling practice, or a real environmental signal.

Before operational use:
- inspect flagged raw records and source metadata;
- account for sampling method, fraction, detection/quantitation limits and result qualifiers;
- assess seasonality and temporal/site dependence;
- compare methods and thresholds for stability;
- validate findings with domain experts and appropriate laboratory/regulatory evidence.

This initial implementation is univariate and parameter-specific. It does not combine unrelated sample events into multivariate vectors. A future multivariate extension should require verified sample-event linkage and harmonised measurement context.
