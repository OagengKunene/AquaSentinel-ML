import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from aquasentinel.features import FEATURES
from aquasentinel.pipeline import build_pipeline

def test_pipeline_fit_and_predict():
    rng=np.random.default_rng(7)
    X=pd.DataFrame(rng.normal(size=(100,len(FEATURES))),columns=FEATURES)
    y=(X["ph"]>X["ph"].median()).astype(int)
    model=build_pipeline(DummyClassifier(strategy="prior")).fit(X,y)
    scores=model.predict_proba(X.iloc[:2])[:,1]
    assert len(scores)==2 and np.all((scores>=0)&(scores<=1))
