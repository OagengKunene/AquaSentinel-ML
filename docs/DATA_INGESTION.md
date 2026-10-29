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

Outputs include the downloaded CSV and an audit report with the immutable dataset revision and checksum. The benchmark's provenance and binary label require critical review; it is not a current regulatory drinking-water determination.

## 3. Track B: current USGS discrete samples

Use the modern USGS Samples API for current USGS discrete water-quality results. The API exposes result profiles, including a compact `narrow` profile. The legacy Water Quality Portal API stopped receiving new/updated USGS discrete data in March 2024. The beta WQP WQX3 service is a separate option when cross-agency coverage is required.

Example (bounded by one known site, a date interval and a characteristic):

```bash
python scripts/download_usgs_samples.py \
  --site-id USGS-04024315 \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --characteristic pH \
  --output data/environmental/usgs_samples.csv
```

Or specify a USGS parameter code:

```bash
python scripts/download_usgs_samples.py \
  --site-id USGS-04024315 \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --usgs-pcode 00400
```

The adapter uses the `results/narrow` profile and preserves the returned CSV bytes unchanged. A neighbouring JSON audit file records the request URL, site/date/parameter scope, retrieval time, returned columns, row count and SHA-256. Requests are bounded to a single USGS site, date range and at least one parameter selector; the default maximum is 100,000 records and the response-size ceiling is 250 MiB. Retry/backoff is applied to transient HTTP failures.

The API's narrow profile is intentionally not transformed into the older WQP schema. Inspect its returned field names before running the existing WQP-specific anomaly scripts; a future adapter should map fields explicitly and retain original columns.

Official documentation:
- [USGS Samples API documentation](https://api.waterdata.usgs.gov/samples-data/docs)
- [USGS Samples API examples and query parameters](https://water.code-pages.usgs.gov/dataRetrieval/reference/read_waterdata_samples.html)
- [USGS/dataRetrieval status notes on legacy WQP freshness](https://water.code-pages.usgs.gov/dataRetrieval/articles/Status.html)

## 4. Historical / multi-agency Water Quality Portal pilot

The existing `scripts/download_wqp_pilot.py` remains a historical legacy-WQP downloader. Do not describe it as a current USGS feed. For current USGS records use the Samples API above; for multi-agency discrete records investigate WQP WQX3 and verify its beta-service status before relying on it.

## 5. South African data track

The Department of Water and Sanitation's Resource Quality Information Services (RQIS) / Water Management System (WMS) publishes selected water-quality results, monitoring-point inventories, eutrophication summaries, microbial assessments and ecosystem data. The DWS portal also indicates that some results are web snapshots and provides a contact route for data requests. This project does not yet claim an automated DWS API integration.

Start with:
- [DWS RQIS / WMS](https://www.dws.gov.za/iwqs/wms/default.aspx)
- [DWS water-quality data and reports](https://www.dwa.gov.za/iwqs/report.aspx)
- [DWS water-quality exploration tool](https://www.dws.gov.za/iwqs/wms/data/000key.asp)
- [Water Research Observatory: South African water-quality sources](https://www.waterresearchobservatory.org/data-and-resources/water-quality)

Before ingesting a South African extract, record its owner, access date, retrieval route, licence/usage terms, update cadence, station identifier, sample/event identifier, parameter, value, unit, method, fraction, detection limit, qualifiers and date/time. Some DWS outputs are snapshots or historical extracts; verify freshness and permitted use with the data owner. Do not scrape or reverse-engineer undocumented interfaces as if they were supported APIs.

## 6. Data handling rules

- Keep raw downloads immutable and separate from derived/cleaned data.
- Do not commit downloaded datasets to Git unless redistribution rights and repository policy have been checked.
- Preserve original parameter identifiers and display names.
- Do not compare unlike units, methods, fractions, qualifiers or sample contexts.
- Discrete samples are not continuous time series; sample-event linkage must be established before combining parameters.
- Anomaly scores indicate unusual observations relative to a defined reference distribution. They do not establish contamination, health risk, safety or regulatory non-compliance.
- Synthetic demo data are for software tests only, not empirical evidence.
