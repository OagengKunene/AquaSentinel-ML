# Benchmark validation: reproducible baseline and threshold analysis

**Status:** live data download, profiling, model training, nested threshold selection and automated tests completed successfully in GitHub Actions on commit `6b5350916273d92fa72220da33e822d2945a3f37`. This is a benchmark experiment, not external scientific validation.

## Data snapshot

- Dataset: [kheejay88/water_potability](https://huggingface.co/datasets/kheejay88/water_potability)
- Dataset revision: `5f896a0b01e0cc25789c0e38eabd7c547c1e92f3`
- File: `water_potability.csv`
- SHA-256: `904004bde729bfe3d2e195f46343bceead09e32a0eb95bb8184e7e20e029b2bf`
- Rows: 3,276; columns: 10; duplicate rows: 0
- Target counts: class 0 = 1,998; class 1 = 1,278
- Missing values: pH = 491 (15.0%); sulfate = 781 (23.8%); trihalomethanes = 162 (4.9%); other features = 0

The dataset card contains minimal metadata. The benchmark label definition and provenance are not sufficient to treat the target as a current regulatory potability determination.

## Evaluation design

- Python 3.11; scikit-learn 1.9.1 in the validation run.
- Stratified 80/20 split, random seed 42: 2,620 training rows and 656 locked holdout rows.
- Candidate model selection used mean 5-fold stratified cross-validation on the training partition only.
- A separate nested 5-fold outer / 4-fold inner CV procedure generated training-only out-of-fold probabilities for threshold analysis. Model selection was repeated inside each outer training fold to reduce threshold-selection optimism.
- The selected final model was refit on the full training partition. Holdout probabilities were generated once and scored at three operating points defined without holdout access.
- Preprocessing (median imputation, missingness indicators, scaling) remained inside each scikit-learn pipeline.
- The primary operating threshold remains 0.5. Two exploratory alternatives are reported: maximum F2, and maximum recall subject to a training OOF precision floor of 0.50.

## Cross-validation comparison

| Candidate | Mean ROC-AUC | Mean average precision | Mean balanced accuracy |
|---|---:|---:|---:|
| Majority-class baseline | 0.5000 | 0.3901 | 0.5000 |
| Random forest | 0.6873 | 0.6017 | 0.6155 |
| HistGradientBoosting | 0.6670 | 0.5786 | 0.6162 |
| Logistic regression | 0.4858 | 0.4000 | 0.4836 |

The random forest was selected by training-partition cross-validation ROC-AUC. Its mean ROC-AUC in the nested outer folds was 0.6768.

## Locked holdout results

| Operating point | Threshold | Accuracy | Balanced accuracy | Precision (class 1) | Recall (class 1) | F1 (class 1) |
|---|---:|---:|---:|---:|---:|---:|
| Default | 0.5000 | 0.6509 | 0.5942 | 0.5931 | 0.3359 | 0.4289 |
| Nested-CV F2 | 0.2099 | 0.4101 | 0.5163 | 0.3981 | 1.0000 | 0.5695 |
| Nested-CV recall with OOF precision floor 0.50 | 0.4070 | 0.6006 | 0.6015 | 0.4905 | 0.6055 | 0.5420 |

Confusion matrices (rows = actual class 0/1; columns = predicted class 0/1):

**Default 0.5**
```text
              Predicted 0   Predicted 1
Actual 0          341            59
Actual 1          170            86
```

**Nested-CV F2 threshold**
```text
              Predicted 0   Predicted 1
Actual 0           13           387
Actual 1            0           256
```

**Precision-constrained alternative**
```text
              Predicted 0   Predicted 1
Actual 0          239           161
Actual 1          101           155
```

The training-selected precision floor is a tuning constraint, not a guarantee: holdout precision at that threshold was 0.4905, slightly below 0.50.

## Interpretation and limitations

The default threshold misses many class-1 examples (recall 33.6%). The F2 operating point captures all 256 positive holdout records, but it also labels 387 of 400 negative records as positive; this is an unacceptable false-alarm burden for many workflows. The precision-constrained alternative improves recall to 60.5% and F1 to 0.5420, with balanced accuracy 0.6015, but precision declines to 49.1% and accuracy to 60.1%. It is a more balanced exploratory trade-off, not proof that the classifier is fit for operational use.

Ranking performance remains modest (holdout ROC-AUC 0.6536; average precision 0.5890). Changing the threshold does not improve ranking quality or the underlying model. These threshold analyses must not be interpreted as water-safety classifications, regulatory determinations or health-risk estimates.

The holdout was not used to select models or thresholds. Do not iterate on thresholds based on these holdout results. Stronger validation requires independent datasets with documented labels and provenance, plus site- or time-aware evaluation. This benchmark contains no site/time grouping information with which to establish generalisation to new locations or future periods.

Permutation importance and calibration diagnostics are included in the machine-readable `evaluation.json` artifact. Feature importance is model-specific and is not evidence of chemical causation.

## Reproduction

```bash
python scripts/download_benchmark.py
python -m scripts.profile_data --data data/benchmark/water_potability.csv --target Potability --output artifacts/benchmark_profile.json
python -m aquasentinel.train --data data/benchmark/water_potability.csv --target Potability --output artifacts/benchmark
pytest -q
```

The GitHub Actions workflow `research-data-validation` uploads the dataset audit, profile, trained model and evaluation JSON as a build artifact. Downloaded data and model artifacts are not committed to Git.
