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

Use the modern USGS Samples API for current USGS discrete water-quality results. The API exposes result profiles, including a compact `narrow` profile. The legacy Water Quality Portal API stopped receiving new/updated USGS discrete data in March 2024.

```bash
python scripts/download_usgs_samples.py --site-id USGS-04024315 --start-date 2020-01-01 --end-date 2020-12-31 --characteristic pH
```

The adapter preserves the returned CSV bytes and writes request provenance, retrieval time, columns, row count and SHA-256. Its schema is not silently coerced into the WQP schema.

## 4. Track C: South African DWS/RQIS exports

### Source selection and limitations

DWS RQIS/WMS is the primary national source for raw surface-water chemistry, eutrophication, microbiology and ecosystem monitoring. The DWS WMS site says that only selected results are available online as snapshots and provides a direct contact for water-quality data requests. The NIWIS water-quality network dashboard is extracted monthly and can lag the underlying WMS database. The WMS database remains the definitive source; a dashboard extract must not be described as a live feed.

Useful entry points:
- [DWS RQIS / Water Management System](https://www.dws.gov.za/iwqs/wms/default.aspx)
- [DWS water-quality results and reports](https://www.dwa.gov.za/iwqs/report.aspx)
- [DWS water-quality exploration tool](https://www.dws.gov.za/iwqs/wms/data/000key.asp)
- [NIWIS Water Quality Monitoring Network](https://www.dws.gov.za/niwis2/WQMN)
- [Water Research Observatory: South African water-quality data](https://www.waterresearchobservatory.org/data-and-resources/water-quality)

The Water Research Observatory documents historical DWS river/dam chemistry datasets for electrical conductivity (EC), pH, nitrate and phosphate, including periods up to 1998 and 1999–2012, plus DWS E. coli data up to October 2024. It also describes a water-chemistry resource with downloadable station CSVs. These are useful research starting points, but check the individual dataset's metadata, release date, provenance and usage terms before treating it as current.

### Requesting the authoritative extract

For station-specific or catchment-specific raw data, request the extract from DWS RQIS rather than scraping an undocumented interface. The RQIS WMS page lists water-quality data requests via **Masilela1T@dws.gov.za**. Include:
- Study purpose and whether use is academic/non-commercial
- Catchment, river/dam, province or monitoring station codes
- Required parameters (e.g. pH, electrical conductivity, nitrate, phosphate)
- Date range and preferred CSV format
- Required metadata: station identifiers and coordinates, sample/event IDs, sample date/time, parameter/determinant codes and names, result values and units, method, fraction, qualifiers, detection/quantitation limits, laboratory/provider and quality flags
- Update cadence, dataset version, licence/permission and attribution wording

Do not commit the received raw data to GitHub until DWS has confirmed the applicable reuse conditions. The NIWIS information page states that DWS retains copyright, use is restricted to academic, research or personal purposes, data may not be resold, and DWS must be acknowledged in publications/electronic media. Verify the terms supplied with the specific extract; do not assume this permission covers commercial use.

### Step 1 — audit the original CSV

Do not guess DWS column names. First run the schema audit:

```bash
python scripts/import_dws_csv.py --input path/to/original_dws_export.csv --dataset-name "DWS RQIS surface-water chemistry"
```

The script leaves the original file unchanged and creates `original_dws_export.csv.audit.json` containing the source checksum, exact headers, row count, blank counts, duplicate rows and review-only mapping suggestions. It does not invent a mapping or silently rename fields.

### Step 2 — explicitly map the observed headers

After inspecting the audit report and source documentation, create a JSON mapping using the *exact* column headers in your CSV. Required canonical keys:

```json
{
  "station_id": "EXACT STATION HEADER",
  "sample_datetime": "EXACT SAMPLE DATE HEADER",
  "parameter_name": "EXACT PARAMETER HEADER",
  "result_value": "EXACT RESULT HEADER",
  "result_unit": "EXACT UNIT HEADER",
  "sample_id": "EXACT SAMPLE/EVENT HEADER",
  "method": "EXACT METHOD HEADER",
  "fraction": "EXACT FRACTION HEADER",
  "detection_limit": "EXACT DETECTION LIMIT HEADER",
  "qualifier": "EXACT QUALIFIER HEADER",
  "provider": "EXACT LAB/PROVIDER HEADER"
}
```

Only include optional keys when those columns exist. Use the actual header strings; the uppercase text above is explanatory, not a real DWS schema.

Then normalize:

```bash
python scripts/import_dws_csv.py \
  --input path/to/original_dws_export.csv \
  --mapping path/to/dws_mapping.json \
  --output data/processed/dws_normalized.csv \
  --dataset-name "DWS RQIS surface-water chemistry" \
  --source-url "https://www.dws.gov.za/iwqs/wms/default.aspx"
```

The normalized file retains all original columns under `raw__...` names, plus the source filename, SHA-256, source row number and source reference. It parses numeric results and timestamps into additional fields but never converts units or drops malformed records. Each row receives a review status; inspect the audit report before downstream analysis. The raw file remains the authoritative source copy.

### Research scope for the first South African pilot

Start with a single river or dam station and a small set of consistently reported parameters such as pH, EC, nitrate and phosphate. These are not interchangeable measurements: retain the original units, method, fraction, detection limits and sample-event context. Do not combine results from different stations or sample events into a single synthetic sample unless the event relationship is established.

## 5. Data handling rules

- Keep raw downloads immutable and separate from derived/cleaned data.
- Do not commit downloaded datasets to Git unless redistribution rights and repository policy have been checked.
- Preserve original parameter identifiers and display names.
- Do not compare unlike units, methods, fractions, qualifiers or sample contexts.
- Discrete samples are not continuous sensor readings.
- Anomaly scores indicate unusual observations relative to a defined reference distribution. They do not establish contamination, health risk, safety or regulatory non-compliance.
- Synthetic demo data are for software tests only, not empirical evidence.

## Official source notes

- [DWS WMS source description and data-request contact](https://www.dws.gov.za/iwqs/wms/default.aspx)
- [NIWIS monitoring-network methodology and monthly extraction limitation](https://www.dws.gov.za/niwis2/Info/WaterQualityMonitoringNetworkInfo)
- [Water Research Observatory: water-quality dataset catalogue](https://www.waterresearchobservatory.org/data-and-resources/water-quality)
