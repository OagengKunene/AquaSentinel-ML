import pandas as pd
import pytest
from aquasentinel.data import load_data
from aquasentinel.features import FEATURES

def test_missing_feature_columns_are_added(tmp_path):
    p=tmp_path/"sample.csv"
    pd.DataFrame({"ph":[6.5,7,7.5,8],"target":[0,1,0,1]}).to_csv(p,index=False)
    X,y,target=load_data(p)
    assert list(X.columns)==FEATURES and len(y)==4 and target=="target"

def test_non_binary_target_rejected(tmp_path):
    p=tmp_path/"bad.csv"
    pd.DataFrame({"ph":[6,7,8],"target":[0,1,2]}).to_csv(p,index=False)
    with pytest.raises(ValueError): load_data(p)
