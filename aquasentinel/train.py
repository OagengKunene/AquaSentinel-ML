import argparse, json
from pathlib import Path
import joblib
import numpy as np
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, classification_report, f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from .data import load_data
from .features import FEATURES
from .pipeline import build_pipeline, candidates


def metrics(y, pred, score):
    return {"accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier_score": float(brier_score_loss(y, score)),
        "classification_report": classification_report(y, pred, output_dict=True, zero_division=0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--target", default=None)
    ap.add_argument("--output", default="artifacts")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    X, y, target = load_data(a.data, a.target)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.2, stratify=y, random_state=a.seed)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=a.seed)
    report = {"project":"AquaSentinel ML", "target":target, "n_samples":len(y),
        "n_train":len(ytr), "n_test":len(yte), "features":FEATURES,
        "warning":"Screening prototype only. Not a certified water-safety assessment.", "models":{}}
    best_name, best_auc, best_model = None, -1, None
    for name, estimator in candidates(a.seed).items():
        model = build_pipeline(estimator)
        cvres = cross_validate(model, Xtr, ytr, cv=cv,
            scoring={"roc_auc":"roc_auc","f1":"f1","balanced_accuracy":"balanced_accuracy"})
        model.fit(Xtr, ytr)
        score = model.predict_proba(Xte)[:, 1]
        pred = (score >= .5).astype(int)
        m = metrics(yte, pred, score)
        report["models"][name] = {"cv_mean":{k:float(np.mean(v)) for k,v in
            ((k, cvres["test_"+k]) for k in ("roc_auc","f1","balanced_accuracy"))},
            "cv_std":{k:float(np.std(cvres["test_"+k])) for k in ("roc_auc","f1","balanced_accuracy")},
            "holdout":m}
        if m["roc_auc"] > best_auc:
            best_name, best_auc, best_model = name, m["roc_auc"], model
    pi = permutation_importance(best_model, Xte, yte, scoring="roc_auc", n_repeats=8,
        random_state=a.seed, n_jobs=1)
    report["selected_model"] = best_name
    report["selection_note"] = "Selected using holdout ROC-AUC for demonstration; use nested validation for rigorous model selection."
    report["permutation_importance"] = sorted([
        {"feature":f, "mean_importance":float(mu), "std":float(sd)}
        for f,mu,sd in zip(FEATURES,pi.importances_mean,pi.importances_std)],
        key=lambda x:x["mean_importance"], reverse=True)
    joblib.dump(best_model, out/"model.joblib")
    (out/"evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"selected_model":best_name,"metrics":report["models"][best_name]["holdout"],
        "warning":report["warning"],"artifacts":str(out.resolve())}, indent=2))


if __name__ == "__main__":
    main()
