# AquaSentinel-ML: Two-Dataset Research Protocol

## Research objective

Develop a reproducible, explainable system for water-quality screening research. The project has two deliberately separate analytical tracks:

1. **Benchmark classification (Track A):** reproduce and critically evaluate a published-style binary water-potability benchmark.
2. **Environmental anomaly screening (Track B):** explore real monitoring observations for unusual measurements, preserving their site, date, parameter, unit, method, and reporting metadata.

The tracks must not be merged into one training table. Track A's binary labels are not transferable to Track B, and an anomaly score is not a potability or contamination label.

## Track A — benchmark classification

### Candidate dataset

Hugging Face dataset: [kheejay88/water_potability](https://huggingface.co/datasets/kheejay88/water_potability).

The dataset is reported as 3,276 records with nine numeric water-quality features and a binary `Potability` target. Its provenance and label-generation process must be independently reviewed before interpreting model results. A dataset-hosting page and a permissive repository licence do not, by themselves, establish scientific validity or drinking-water regulatory status.

### Required ingestion checks

- Record the dataset repository, file path, immutable dataset revision/commit, retrieval date, and licence metadata.
- Preserve an unmodified copy of the downloaded source and its SHA-256 checksum.
- Validate row/column counts, expected feature names, target values, duplicate rows, missingness, numeric coercion, and plausible value ranges.
- Produce a data dictionary and a machine-readable dataset audit report.
- Never replace missing values or remove outliers silently; document each transformation.

### Evaluation design

- Reserve a stratified holdout set before model comparison and do not use it to select models or tune thresholds.
- Perform preprocessing inside each cross-validation fold to prevent leakage.
- Compare a simple baseline (majority class and regularised logistic regression) with tree-based models.
- Report ROC-AUC, average precision, precision, recall, F1, balanced accuracy, confusion matrix, and probability calibration (including Brier score).
- Select models and operating thresholds using training/validation data only; evaluate the locked choice once on the holdout set.
- Discuss class imbalance and the consequences of false negatives and false positives. Do not optimise accuracy alone.

### Interpretation boundary

The benchmark target is not assumed to be equivalent to a current legal drinking-water standard. Scores are research outputs and cannot certify water as safe or unsafe.

## Track B — real environmental observations

### Candidate sources

- [Water Quality Portal](https://www.waterqualitydata.us/), which provides discrete water-quality sample results contributed by multiple agencies.
- [USGS Water Data APIs](https://api.waterdata.usgs.gov/), including monitoring-location, continuous/daily, and water-quality resources. For current USGS discrete samples, use the USGS Samples API or beta WQP WQX3 services; the legacy WQP API stopped receiving new/updated USGS discrete-water-quality records in March 2024.

Prefer current APIs and preserve source-specific identifiers. Do not build new ingestion around deprecated legacy endpoints.

### Sampling and harmonisation rules

- Begin with a small, reproducible pilot query and document geography, date range, providers, sites, and requested characteristics.
- Keep each raw source response unchanged alongside a normalised analytical table.
- Preserve at minimum: monitoring location/site ID, sample or activity ID, collection date/time, characteristic/parameter, result value, unit, analytical method, fraction, detection/quantification limit, provider, and source record identifier where available.
- Do not compare or pool measurements merely because their display names look similar. Harmonise parameter identifiers, units, methods, fractions, and sample context explicitly.
- Do not pivot unrelated sample events into a synthetic row. Only create multivariate sample vectors when measurements can be defensibly linked to the same sampling event and compatible context.
- Where repeated observations are available, retain temporal and site grouping for validation. Where they are not, use parameter-specific analysis rather than pretending the data form a continuous time series.

### Anomaly analysis

Start with transparent baselines (robust z-scores and parameter-specific distribution checks), then compare suitable unsupervised methods such as Isolation Forest and Local Outlier Factor. Evaluate stability across sites/time periods, sensitivity to data cleaning, and agreement with domain review where possible.

An anomaly means unusual relative to the comparison data and chosen method. It does **not** establish contamination, a health risk, a regulatory exceedance, or unsafe drinking water. Regulatory interpretation requires the relevant jurisdiction, parameter, units, sampling method, and applicable standard.

## Reproducibility and reporting

Every experiment should record:

- source URL and immutable source revision or query parameters;
- retrieval timestamp and raw-file checksum;
- data dictionary, inclusion/exclusion rules, and missing-data treatment;
- random seeds, package versions, model configuration, and validation split strategy;
- metrics with uncertainty where feasible, limitations, and known sources of bias.

Synthetic data generated by `scripts/generate_demo_data.py` are for software smoke tests only. They must never be reported as empirical water-quality evidence or used to claim real-world model performance.

## Planned milestones

1. **Data provenance foundation:** implement benchmark download/audit and document the Track B query contract.
2. **Exploratory analysis:** missingness, distributions, duplicates, ranges, site/time coverage, and data-quality limitations.
3. **Leakage-safe modelling:** establish baselines and robust validation for each track independently.
4. **Explainability and review:** feature-level explanations for Track A; parameter/site/time context for Track B.
5. **Deployment:** publish a carefully scoped model card and a Hugging Face Space only after the data and evaluation limitations are clearly documented.

## Research integrity

AquaSentinel-ML is a research and educational screening prototype. It is not a certified laboratory, regulatory decision system, or substitute for accredited water testing and qualified public-health/environmental professionals.
