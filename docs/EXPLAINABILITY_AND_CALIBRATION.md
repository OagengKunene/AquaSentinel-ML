# Model explainability and calibration

## Calibration diagnostics

The classifier training report includes quantile-binned holdout calibration data. Each bin reports its mean predicted positive-class score and observed positive fraction. The Brier score is also retained.

Calibration is descriptive and does not guarantee calibrated probabilities on future sites, time periods or populations. The benchmark target itself has provenance and label-definition limitations.

## SHAP explanations

SHAP is optional so the core training and API installation remains lightweight.

Install the optional extra:

```bash
pip install -e ".[explain]"
```

Explain a saved model using a separate CSV with the same nine feature columns:

```bash
python -m scripts.explain_model --model artifacts/model.joblib --data data/benchmark/explanation_rows.csv --background-size 40 --explain-size 100
```

The output JSON contains global mean absolute SHAP values and the five largest signed contributions for each explained row. Positive SHAP values push the model score upward; negative values push it downward, relative to the chosen background.

## Interpretation and leakage safeguards

- Use a representative background dataset and document how it was selected.
- Prefer external or separately reserved explanation rows.
- Do not use explanations from a final holdout to redesign the model and then report that same holdout as an untouched final evaluation.
- SHAP explains model behaviour, not causal relationships or chemical mechanisms.
- A high contribution does not establish that a measurement is harmful or violates a drinking-water standard.
- SHAP scores and model outputs are conditional on the benchmark's labels, features and sampling limitations.
