# AquaSentinel ML — Explainable Water-Quality Risk Screening

An end-to-end machine-learning project for a global technical problem: helping environmental teams prioritize water samples for laboratory review. Includes data validation, preprocessing pipelines, model comparison, cross-validation, holdout metrics, permutation importance, a FastAPI service, a Streamlit dashboard, tests and Docker support.

**Critical limitation:** this is a research/educational prototype, not a certified drinking-water test. Predictions cannot establish that water is safe or unsafe. Synthetic demo data is only for software smoke tests; never use its scores as evidence of real-world performance.

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

## Real-data experiment
Download a public water potability dataset from a trusted source, review its license and label definition, then run:
```bash
python -m aquasentinel.train --data data/water_quality.csv --target Potability
```
Expected numeric features (missing columns are imputed): `ph, Hardness, Solids, Chloramines, Sulfate, Conductivity, Organic_carbon, Trihalomethanes, Turbidity`. Target must be binary 0/1.

## API
`POST /predict` accepts these measurement fields. Example:
```json
{"ph":7.2,"Hardness":180,"Solids":12000,"Chloramines":6,"Sulfate":300,"Conductivity":400,"Organic_carbon":10,"Trihalomethanes":60,"Turbidity":3}
```
Returns a model score and screening-priority label, not a verified probability of contamination.

## Technical design
- Scikit-learn preprocessing pipeline (median imputation, missingness indicators, scaling).
- Random Forest, HistGradientBoosting and Logistic Regression candidates.
- Stratified 5-fold CV plus untouched holdout evaluation: ROC-AUC, average precision, F1, balanced accuracy, precision, recall and Brier score.
- Permutation feature importance and persisted model/report artifacts.
- API, interactive dashboard, synthetic data generator and unit tests.

## Research and deployment cautions
Random splits may overestimate performance when samples are clustered by time/site. Prefer external, site/time-based validation where possible. Thresholds require domain-expert review and explicit false-negative/false-positive cost analysis. Before production: add authentication, rate limiting, monitoring, data provenance, validated calibration, robust model versioning, privacy controls and independent scientific validation. Never use this tool as a substitute for accredited laboratory testing or local public-health advice.
