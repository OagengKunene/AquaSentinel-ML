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

## Exploratory data analysis\n\nProfile either downloaded dataset without modifying the raw file:\n\n```bash\n# Track A: include the binary target\npython -m scripts.profile_data --data data/benchmark/water_potability.csv --target Potability\n\n# Track B: descriptive profile only; do not treat records as a continuous time series\npython -m scripts.profile_data --data data/environmental/wqp_results.csv --output artifacts/wqp_profile.json\n```\n\nThe report includes missingness, duplicate rows, numeric summaries and correlations. For WQP data it also reports common parameter/provider values when those columns exist. These are exploratory summaries, not data harmonisation or regulatory assessments.\n\n## Track B: environmental anomaly screening\n\nAfter downloading a bounded Water Quality Portal dataset, run the parameter-aware anomaly screen:\n\n```bash\npython -m scripts.anomaly_screen --data data/environmental/wqp_results.csv --scope site --min-samples 30\n```\n\nThis adds robust median/MAD scores, Isolation Forest flags and Local Outlier Factor flags within characteristic/unit/site groups. Small groups are skipped. The default site scope avoids pooling naturally different monitoring locations. These are exploratory statistical signals, not evidence of contamination or unsafe water. See [Anomaly Screening Methodology](docs/ANOMALY_SCREENING.md).\n\n## Existing demo experiment

Generate synthetic smoke-test data and run the existing pipeline:

```bash
python scripts/generate_demo_data.py
python -m aquasentinel.train --data data/demo_water_quality.csv --target potability
```

Expected numeric features: `ph, Hardness, Solids, Chloramines, Sulfate, Conductivity, Organic_carbon, Trihalomethanes, Turbidity`. Target must be binary 0/1.

**Methodology note:** model selection now uses mean cross-validation ROC-AUC on the training partition. The selected model is refit on that partition and the holdout is evaluated once at a predeclared 0.5 threshold. Preprocessing remains inside the scikit-learn pipeline and therefore inside each CV fold. Do not repeatedly inspect or tune against the holdout. This random-split experiment still does not establish performance on new sites or future time periods.

Run tests with `pytest -q`; GitHub Actions runs the same suite on pushes and pull requests.\n\n## API

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
