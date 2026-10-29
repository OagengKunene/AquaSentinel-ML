# AquaSentinel ML — Explainable Water-Quality Risk Screening

An end-to-end machine-learning project for a global technical problem: helping environmental teams prioritize water samples for laboratory review. Includes data validation, preprocessing pipelines, model comparison, cross-validation, holdout metrics, permutation importance, a FastAPI service, a Streamlit dashboard, tests and Docker support.

**Critical limitation:** this is a research/educational prototype, not a certified drinking-water test. Predictions cannot establish that water is safe or unsafe. Synthetic demo data is only for software smoke tests; never use its scores as evidence of real-world performance.

## Research design: two independent data tracks

AquaSentinel uses two distinct analytical tracks. Their records and labels must not be merged.

- **Track A — benchmark classification:** a public Hugging Face water-potability benchmark with a binary target. Its dataset provenance and label definition require critical review; the target is not assumed to represent a current regulatory drinking-water determination.
- **Track B — environmental anomaly screening:** discrete sample observations from the Water Quality Portal and, where suitable, USGS water-data services. Site, sample-event, date, parameter, unit, method and detection-limit metadata must be retained. An anomaly is not proof of contamination or health risk.

See [Research Protocol](docs/RESEARCH_PROTOCOL.md) and [Data Ingestion Guide](docs/DATA_INGESTION.md).

## Quick start (Python 3.11+)

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_demo_data.py
python -m aquasentinel.train --data data/demo_water_quality.csv --target potability
uvicorn aquasentinel.api:app --reload
```

API docs: http://127.0.0.1:8000/docs

In another terminal: `streamlit run dashboard/app.py`. Tests: `pytest -q`.

## Download research datasets

Track A benchmark:

```bash
python scripts/download_benchmark.py
```

This saves the CSV under `data/benchmark/` and an audit report under `artifacts/`, including the resolved Hugging Face revision and SHA-256 checksum.

Track B Water Quality Portal pilot (choose a bounded site or state scope, date range and characteristic):

```bash
python scripts/download_wqp_pilot.py --siteid USGS-01594440 --start-date 2020-01-01 --end-date 2020-12-31 --characteristic "Dissolved oxygen"
```

The script preserves the raw CSV and writes query provenance beside it. See the ingestion guide for additional options and interpretation constraints. Downloaded CSV data is excluded from Git by default.

## Existing demo experiment

Generate synthetic smoke-test data and run the existing pipeline:

```bash
python scripts/generate_demo_data.py
python -m aquasentinel.train --data data/demo_water_quality.csv --target potability
```

Expected numeric features: `ph, Hardness, Solids, Chloramines, Sulfate, Conductivity, Organic_carbon, Trihalomethanes, Turbidity`. Target must be binary 0/1.

**Methodology note:** the current training implementation is an initial prototype. Before publishing benchmark performance, model selection and threshold decisions must be made without using the final holdout set; preprocessing must remain inside cross-validation folds. This is a planned research-hardening task.

## API

`POST /predict` accepts these measurement fields. Example:

```json
{"ph":7.2,"Hardness":180,"Solids":12000,"Chloramines":6,"Sulfate":300,"Conductivity":400,"Organic_carbon":10,"Trihalomethanes":60,"Turbidity":3}
```

Returns a model score and screening-priority label, not a verified probability of contamination.

## Technical design

- Scikit-learn preprocessing pipeline (median imputation, missingness indicators, scaling).
- Random Forest, HistGradientBoosting and Logistic Regression candidates.
- Stratified 5-fold CV and holdout evaluation metrics, with evaluation design under active hardening.
- Permutation feature importance and persisted model/report artifacts.
- API, interactive dashboard, synthetic data generator and unit tests.

## Research and deployment cautions

Random splits may overestimate performance when samples are clustered by time/site. Prefer external, site/time-based validation where possible. Thresholds require domain-expert review and explicit false-negative/false-positive cost analysis. Do not compare environmental measurements without checking parameter identifiers, units, methods, fractions and sample context. Before production: add authentication, rate limiting, monitoring, data provenance, validated calibration, robust model versioning, privacy controls and independent scientific validation. Never use this tool as a substitute for accredited laboratory testing or local public-health advice.
