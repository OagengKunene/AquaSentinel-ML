from pathlib import Path
import joblib
import pandas as pd
from .features import FEATURES


def load_model(path="artifacts/model.joblib"):
    if not Path(path).exists():
        raise FileNotFoundError(f"Model not found at {path}; train one first")
    return joblib.load(path)


def score(model, sample, threshold=.5):
    X = pd.DataFrame([{f: sample.get(f) for f in FEATURES}], columns=FEATURES)
    p = float(model.predict_proba(X)[0, 1])
    return {"screening_score":p,
        "screening_label":"higher_screening_priority" if p >= threshold else "lower_screening_priority",
        "threshold":threshold,
        "warning":"Research screening only. This is not proof of water safety or contamination."}
