# Data ingestion guide

The project intentionally stores benchmark labels and environmental observations separately.

## 1. Install dependencies

Use Python 3.11 or newer:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Track A: Hugging Face benchmark

```bash
python scripts/download_benchmark.py
```

Outputs:
- `data/benchmark/water_potability.csv`: downloaded source data.
- `artifacts/benchmark_audit.json`: source revision, retrieval time, checksum, row/column counts, label counts, duplicates, missingness, and descriptive statistics.

The script resolves the current dataset revision through the Hugging Face Hub API, then downloads the CSV at that immutable revision. The dataset repository currently identifies its licence as MIT, but its dataset card is minimal; the scientific provenance and meaning of its binary label require further investigation. Do not interpret its target as a current regulatory drinking-water determination.

## 3. Track B: Water Quality Portal pilot

Choose a small, explicit site or state scope, date interval, and characteristic. Example using a USGS site:

```bash
python scripts/download_wqp_pilot.py \
  --siteid USGS-01594440 \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --characteristic "Dissolved oxygen" \
  --output data/environmental/wqp_results.csv
```

Example using a state code (replace with a suitable US state code):

```bash
python scripts/download_wqp_pilot.py \
  --statecode US:55 \
  --start-date 2020-01-01 \
  --end-date 2020-03-31 \
  --characteristic "Dissolved oxygen" \
  --characteristic "pH" \
  --max-records 100000
```

Outputs:
- Raw WQP CSV, unchanged.
- A neighbouring `.metadata.json` file with the exact query URL, scope, dates, retrieval timestamp, row count, columns, and checksum.

The Water Quality Portal provides discrete sample observations contributed by multiple agencies. A query may return measurements with different methods, fractions, units, detection limits, and sample contexts. Inspect the columns and metadata before any harmonisation. Never pivot unrelated records into one artificial sample vector.

## 4. Data handling rules

- Do not commit downloaded datasets or derived sensitive data to Git unless redistribution rights and repository policy have been checked. The default `.gitignore` excludes CSV files under `data/`.
- Keep the raw data immutable. Perform cleaning and unit conversion into separate derived files with documented transformations.
- Record parameter identifiers as well as display names where available.
- Use parameter-specific analysis until sample-event linkage and unit/method compatibility are established.
- Anomaly scores indicate unusual observations relative to a defined reference distribution; they do not establish contamination, a health risk, or regulatory non-compliance.
- Synthetic demo data are for software tests only and are not empirical evidence.
