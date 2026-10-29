import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from aquasentinel import train
from aquasentinel.features import FEATURES


def test_training_selects_on_cv_and_writes_artifacts(tmp_path, monkeypatch):
    rng = np.random.default_rng(19)
    count = 100
    frame = pd.DataFrame(
        rng.normal(size=(count, len(FEATURES))),
        columns=FEATURES,
    )
    frame["ph"] += np.linspace(-2, 2, count)
    frame["Potability"] = (frame["ph"] > 0).astype(int)
    data_path = tmp_path / "benchmark.csv"
    frame.to_csv(data_path, index=False)

    monkeypatch.setattr(
        train,
        "candidates",
        lambda seed: {"logistic_regression": LogisticRegression(max_iter=1000)},
    )
    report = train.run_experiment(
        data_path,
        target="Potability",
        output=tmp_path / "artifacts",
        seed=7,
    )

    assert report["selected_model"] == "logistic_regression"
    assert "holdout" in report
    assert "roc_auc" in report["holdout"]
    assert "selected_model_cv_mean_roc_auc" in report
    assert "not used to choose the model" in report["selection_note"]
    assert (tmp_path / "artifacts" / "model.joblib").exists()
    evaluation_path = tmp_path / "artifacts" / "evaluation.json"
    assert evaluation_path.exists()
    saved_report = json.loads(evaluation_path.read_text(encoding="utf-8"))
    assert saved_report["n_samples"] == count
