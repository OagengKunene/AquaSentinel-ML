import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aquasentinel.features import FEATURES

def main():
    p=argparse.ArgumentParser(description="Generate SYNTHETIC smoke-test data, not real water data.")
    p.add_argument("--output",default="data/demo_water_quality.csv")
    p.add_argument("--samples",type=int,default=1200)
    p.add_argument("--seed",type=int,default=42)
    a=p.parse_args()
    if a.samples < 100: p.error("--samples must be >=100")
    X,y=make_classification(n_samples=a.samples,n_features=len(FEATURES),n_informative=6,
        n_redundant=1,weights=[.58,.42],class_sep=.8,flip_y=.04,random_state=a.seed)
    rng=np.random.default_rng(a.seed)
    scales=np.array([2.2,80,8000,2,100,180,5,30,1.4])
    offsets=np.array([7,180,12000,6,300,400,10,60,3])
    df=pd.DataFrame(X*scales+offsets,columns=FEATURES)
    df["ph"]=df["ph"].clip(0,14); df["potability"]=y
    for col in ("ph","Sulfate","Trihalomethanes"):
        df.loc[rng.random(a.samples)<.08,col]=np.nan
    path=Path(a.output); path.parent.mkdir(parents=True,exist_ok=True); df.to_csv(path,index=False)
    print(f"Wrote {len(df)} SYNTHETIC rows to {path}; metrics are not real-world evidence.")
if __name__=="__main__": main()
