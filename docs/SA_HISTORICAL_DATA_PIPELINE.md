# South African historical water-chemistry pipeline

This workflow combines the WRO station workbook with the separate Rivers and
Dams & Lakes historical chemistry workbooks. It creates a reproducible,
wide-format CSV and a JSON data-quality/provenance report.

## Inputs

Keep the three original XLSX files outside the repository. Do not commit raw
workbooks unless their redistribution terms explicitly permit it.

- Sample stations workbook (Sample stations.xlsx)
- Rivers 1999–2012 workbook
- Dams and lakes 1999–2012 workbook

Expected worksheet layouts:

- Station metadata: Sample stations with ID, Samples stations with Z-ID,
  and Sample stations without ID; headers are on Excel row 1.
- River chemistry: Rivers; field labels are on row 3 and units on row 2.
- Dam/lake chemistry: Dams & Lakes; field labels are on row 3 and units on row 2.

The station workbook's “without details” sheet is not used for metadata joins
because it contains identifiers only. Its IDs are not silently promoted to
fully described stations.

## Install and run

Install project dependencies, including the Excel reader:

```bash
pip install -r requirements.txt
python scripts/build_sa_historical_dataset.py --stations path/to/water_sample_stations.xlsx --rivers path/to/rivers_water_chemistry.xlsx --dams-lakes path/to/dams_lakes_water_chemistry.xlsx --output data/processed/sa_historical_water_chemistry.csv --report artifacts/sa_historical_data_quality.json
```

The generated CSV and JSON report are ignored by the repository's existing
.gitignore rules for data CSVs and artifacts. Keep source files and generated
research data local unless the applicable data licence permits redistribution.

## Output structure

The combined CSV retains all 44 chemistry fields in wide form, plus:

- Waterbody type: river or dam_lake
- Source workbook, worksheet and Excel row number
- Original station ID and point ID
- Parsed sample date and source year
- Station match status
- Matched station ID, waterbody description, locality, decimal coordinates,
  drainage region and station date bounds
- Chemistry measurements with unique, normalized output column names

The JSON report records input file names, byte sizes and SHA-256 checksums;
station-index counts; per-dataset row and date coverage; point-ID match counts;
exact duplicate rows; repeated station/point/date groups; blank and sentinel
counts; source field labels and units; and the output checksum.

## Data handling and interpretation

- Original workbooks are opened read-only and are never modified.
- The station join uses POINT ID only when it resolves to exactly one station
  row. Ambiguous, missing and unmatched IDs remain in the output and are
  explicitly labelled; the pipeline does not guess a match using locality text.
- The -9999 sentinel (including numeric -9999.0) is converted to an empty
  output cell and counted by measurement field in the report. The source file
  remains unchanged.
- Original measurement values and units are not converted or imputed.
- No rows are removed, even when exact duplicates are detected. Repeated
  station/point/date groups are reported for review, not automatically merged.
- River and dam/lake records remain distinguished by waterbody_type.
- Discrete historical samples are not continuous sensor readings. Sampling
  frequency, analytical methods, detection limits, qualifiers and sample
  context must be considered before comparing measurements.

This is a historical research dataset, not a certified drinking-water test.
An anomaly score is a statistical screening signal; it does not establish
contamination, unsafe water, health risk or regulatory non-compliance. Verify
the source dataset's licence and reuse conditions before redistribution or
commercial use.
