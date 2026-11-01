# AquaSentinel ML — Explainable Water-Quality Risk Screening

An end-to-end machine-learning project for helping environmental teams prioritize water samples for laboratory review. Includes data validation, preprocessing pipelines, model comparison, cross-validation, holdout metrics, explainability, anomaly screening, API/dashboard foundations and tests.

**Critical limitation:** this is a research/educational prototype, not a certified drinking-water test. Predictions cannot establish that water is safe or unsafe. Synthetic demo data is only for software smoke tests; never use its scores as evidence of real-world performance.

## Research design: independent data tracks

AquaSentinel uses distinct analytical tracks. Their records and labels must not be merged.

- **Track A — benchmark classification:** a public Hugging Face water-potability benchmark with a binary target. Its provenance and label definition require critical review; the target is not assumed to represent a current regulatory drinking-water determination.
- **Track B — environmental anomaly screening:** discrete sample observations from USGS and the Water Quality Portal, with South African historical chemistry now supported as a separate research dataset. Site, sample-event, date, parameter, unit, method and detection-limit metadata must be retained. An anomaly is not proof of contamination or health risk.

See [Research Protocol](docs/RESEARCH_PROTOCOL.md), [Data Ingestion Guide](docs/DATA_INGESTION.md), and [South African Historical Data Pipeline](docs/SA_HISTORICAL_DATA_PIPELINE.md).

## Quick start (Python 3.11+)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_demo_data.py
python -m aquasentinel.train --data data/demo_water_quality.csv --target potability
uvicorn aquasentinel.api:app --reload
```

API docs: http://127.0.0.1:8000/docs

In another terminal: `streamlit run dashboard/app.py`. Tests: `pytest -q`.

## Download research datasets

### Track A: Hugging Face benchmark

```bash
python scripts/download_benchmark.py
```

This saves the CSV under `data/benchmark/` and an audit report under `artifacts/`, including the resolved immutable Hugging Face revision and SHA-256 checksum.

### Track B1: current USGS discrete water-quality samples

Use the modern USGS Samples API adapter (not the legacy WQP endpoint) for current USGS discrete observations:

```bash
python scripts/download_usgs_samples.py --site-id USGS-04024315 --start-date 2020-01-01 --end-date 2020-12-31 --characteristic pH --output data/environmental/usgs_samples.csv
```

The query must specify a single USGS site, date interval and characteristic or USGS parameter code. The script retains the raw CSV unchanged and writes a neighbouring metadata JSON containing the exact request URL, retrieval time, query scope, columns, row count and checksum. Transient HTTP failures use bounded retries; record count and response size are capped. See [Data Ingestion Guide](docs/DATA_INGESTION.md).

### Track B2: historical / multi-agency Water Quality Portal pilot

The existing `scripts/download_wqp_pilot.py` targets the legacy WQP Result service. It remains useful for historical extraction, but legacy USGS discrete records stopped receiving new/updated data in March 2024. Do not treat it as a current USGS feed. Use the USGS Samples API above for current USGS discrete data; evaluate the beta WQP WQX3 service separately for cross-agency coverage.

### Track B3: South African historical river and dam/lake chemistry

A reproducible pipeline now combines the WRO station workbook with its separate Rivers and Dams & Lakes chemistry workbooks:

```bash
python scripts/build_sa_historical_dataset.py --stations path/to/water_sample_stations.xlsx --rivers path/to/rivers_water_chemistry.xlsx --dams-lakes path/to/dams_lakes_water_chemistry.xlsx --output data/processed/sa_historical_water_chemistry.csv --report artifacts/sa_historical_data_quality.json
```

It preserves every source measurement row, links station metadata only through unique point IDs, retains original units, records unmatched/ambiguous identifiers and duplicate observations, and reports source checksums and missing-value sentinels. The -9999 sentinel becomes a blank derived CSV cell and is counted in the audit report; original XLSX files remain unchanged. Raw source files and generated datasets must stay out of Git unless the dataset-specific reuse terms permit redistribution. See [South African Historical Data Pipeline](docs/SA_HISTORICAL_DATA_PIPELINE.md).

### Track B4: South African DWS/RQIS CSV exports

A South African import workflow is available for real DWS/RQIS extracts. First audit the exact schema without guessing column names:

```bash
python scripts/import_dws_csv.py --input path/to/original_dws_export.csv --dataset-name "DWS RQIS water-quality extract"
```

Inspect the generated `.audit.json`, then create an explicit JSON mapping using the exact source headers before normalizing. The adapter preserves every original column, source checksum, row number, original units and malformed rows for review. See [Data Ingestion Guide](docs/DATA_INGESTION.md) and the [DWS data request email template](docs/DWS_DATA_REQUEST.md).

DWS/RQIS online data can be historical snapshots; the NIWIS water-quality network dashboard is extracted monthly and may lag the underlying WMS database. Verify the specific dataset's provenance, date coverage, licence and reuse conditions. Do not commit raw DWS records to GitHub without permission. Anomaly flags are not regulatory or drinking-water safety determinations.

## Existing anomaly workflows

The WQP-specific cross-sectional and temporal scripts remain available for datasets with compatible WQP column names:

```bash
python -m scripts.anomaly_screen --data data/environmental/wqp_results.csv --scope site --min-samples 30
python -m scripts.temporal_anomaly --data data/environmental/wqp_results.csv --min-history 20 --lookback 60 --threshold 3.5
```

The new USGS narrow profile and South African historical workbook output are not silently renamed into the legacy WQP schema. Inspect their columns and implement an explicit, tested mapping before using WQP-specific workflows. Flags are exploratory statistical signals, not evidence of contamination or unsafe water.

## Model methodology and limitations

The supervised benchmark uses a training-partition model-selection process and nested cross-validation for exploratory threshold analysis. Holdout data are not used to choose the model or operating thresholds. A random split does not establish performance on new sites or future time periods. Thresholds are not water-safety cutoffs.

Before production: add site/time-based external validation, expert review, validated calibration, monitoring, model versioning, privacy controls and independent scientific validation. Never use this tool as a substitute for accredited laboratory testing or local public-health advice.
