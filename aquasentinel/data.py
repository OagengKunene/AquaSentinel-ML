import pandas as pd
from .features import FEATURES


def load_data(path, target=None):
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("Dataset is empty")
    target = target or next((c for c in ("potability", "Potability", "target", "label") if c in df), None)
    if not target or target not in df:
        raise ValueError("Binary target column not found; pass --target")
    y = pd.to_numeric(df[target], errors="coerce")
    keep = y.notna()
    y = y[keep].astype(int)
    if not set(y.unique()).issubset({0, 1}) or y.nunique() != 2:
        raise ValueError("Target must contain both binary classes 0 and 1")
    for col in FEATURES:
        if col not in df:
            df[col] = float("nan")
    X = df.loc[keep, FEATURES].apply(pd.to_numeric, errors="coerce")
    if X.isna().all().all():
        raise ValueError("All expected feature values are missing/non-numeric")
    return X, y, target
