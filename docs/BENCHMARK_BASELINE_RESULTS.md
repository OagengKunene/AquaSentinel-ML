# Benchmark validation: initial baseline

**Status:** the data download, profiling, model training, and automated tests completed successfully in GitHub Actions. This is a first benchmark experiment, not external scientific validation.

## Data snapshot

- Dataset: [kheejay88/water_potability](https://huggingface.co/datasets/kheejay88/water_potability)
- Dataset revision: `5f896a0b01e0cc25789c0e38eabd7c547c1e92f3`
- File: `water_potability.csv`
- SHA-256: `904004bde729bfe3d2e195f46343bceead09e32a0eb95bb8184e7e20e029b2bf`
- Rows: 3,276; columns: 10; duplicate rows: 0
- Target counts: class 0 = 1,998; class 1 = 1,278
- Missing values: pH = 491 (15.0%); sulfate = 781 (23.8%); trihalomethanes = 162 (4.9%); other features = 0
- Target values were complete and restricted to 0 and 1.

The dataset card contains only minimal metadata. The benchmark label definition and provenance are not sufficient to treat the target as a current regulatory potability determination.

## Evaluation design

- Python 3.11; scikit-learn 1.9.1 in the validation run.
- Stratified 80/20 split, random seed 42: 2,620 training rows and 656 holdout rows.
- Candidate selection used mean 5-fold stratified cross-validation on the training partition only.
- The selected model was refit on the training partition and evaluated once on the holdout.
- The classification threshold was fixed at 0.5 before holdout evaluation.
- Preprocessing (median imputation, missingness indicators, scaling) remained inside each scikit-learn pipeline.
- The holdout was not used to select the model or threshold.

## Cross-validation comparison

| Candidate | Mean ROC-AUC | Mean average precision | Mean balanced accuracy |
|---|---:|---:|---:|
| Majority-class baseline | 0.5000 | 0.3901 | 0.5000 |
| Random forest | 0.6873 | 0.6017 | 0.6155 |
| HistGradientBoosting | 0.6670 | 0.5786 | 0.6162 |
| Logistic regression | 0.4858 | 0.4000 | 0.4836 |

The random forest was selected by training-partition cross-validation ROC-AUC.

## Locked holdout results

| Metric | Result |
|---|---:|
| Accuracy | 0.6509 |
| Balanced accuracy | 0.5942 |
| Precision (class 1) | 0.5931 |
| Recall (class 1) | 0.3359 |
| F1 (class 1) | 0.4289 |
| ROC-AUC | 0.6536 |
| Average precision | 0.5890 |
| Brier score | 0.2184 |

Confusion matrix (rows = actual class 0/1; columns = predicted class 0/1):

```text
              Predicted 0   Predicted 1
Actual 0          341            59
Actual 1          170            86
```

## Interpretation

The model shows a modest ranking signal over the majority-class baseline, but its holdout discrimination is materially lower than its training cross-validation estimate. At the fixed 0.5 threshold it identifies only 33.6% of class-1 holdout records (86 of 256). This is not a reliable classifier for consequential decisions and should not be deployed as a water-safety decision system.

Do not tune the threshold against this holdout. Any threshold analysis must use a separate validation process, with explicit costs for false positives and false negatives. Stronger validation would require independent datasets, documented label provenance, and (for real environmental observations) site- or time-aware evaluation. The current benchmark has no site/time grouping information with which to establish generalisation to new locations or future periods.

Permutation importance and calibration diagnostics are included in the machine-readable `evaluation.json` artifact produced by the validation workflow. Feature importance is model-specific and is not evidence of chemical causation.

## Reproduction

Run:

```bash
python scripts/download_benchmark.py
python -m scripts.profile_data --data data/benchmark/water_potability.csv --target Potability --output artifacts/benchmark_profile.json
python -m aquasentinel.train --data data/benchmark/water_potability.csv --target Potability --output artifacts/benchmark
pytest -q
```

The GitHub Actions workflow `research-data-validation` uploads the dataset audit, profile, trained model, and evaluation JSON as a build artifact. Downloaded data and model artifacts are not committed to Git.
