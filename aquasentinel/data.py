import pandas as pd
from .features import FEATURES


def load_data(path, target=None):
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("Dataset is empty")
    target = target or next((c for c in ("potability", "Potability", "target", "label") if c in df), None)
    if not target or target not in df:
        raise ValueError("Binary target column not found; pass --target")
    raw_y = pd.to_numeric(df[target], errors="coerce")
    if raw_y.isna().any():
        raise ValueError("Target contains missing or non-numeric values")
    if not raw_y.isin([0, 1]).all() or raw_y.nunique() != 2:
        raise ValueError("Target must contain both binary classes 0 and 1")
    y = raw_y.astype(int)
    for col in FEATURES:
        if col not in df:
            df[col] = float("nan")
    X = df.loc[:, FEATURES].apply(pd.to_numeric, errors="coerce")
    if X.isna().all().all():
        raise ValueError("All expected feature values are missing/non-numeric")
    return X, y, target
