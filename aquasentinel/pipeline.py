from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from .features import FEATURES


def build_pipeline(estimator):
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler())])
    prep = ColumnTransformer([("numeric", numeric, FEATURES)], remainder="drop")
    return Pipeline([("preprocess", prep), ("model", estimator)])


def candidates(seed=42):
    return {
        "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
            class_weight="balanced_subsample", max_features="sqrt", n_jobs=-1, random_state=seed),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=180, learning_rate=.07,
            l2_regularization=1.0, random_state=seed),
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced", C=.5),
    }
