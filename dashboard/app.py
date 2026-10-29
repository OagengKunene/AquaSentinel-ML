import json, sys
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from aquasentinel.features import FEATURES
from aquasentinel.predict import load_model, score

st.set_page_config(page_title="AquaSentinel ML",page_icon="💧",layout="wide")
st.title("💧 AquaSentinel ML")
st.caption("Explainable water-quality screening research prototype")
st.warning("This does not determine whether water is safe to drink. Use accredited laboratory tests and local public-health guidance.")
model_path=ROOT/"artifacts"/"model.joblib"; report_path=ROOT/"artifacts"/"evaluation.json"
if not model_path.exists():
    st.info("No model yet. Follow README quick-start to generate synthetic demo data and train.")
    st.stop()
ranges={"ph":(0.,14.,7.),"Hardness":(0.,1000.,180.),"Solids":(0.,100000.,12000.),
"Chloramines":(0.,30.,6.),"Sulfate":(0.,2000.,300.),"Conductivity":(0.,3000.,400.),
"Organic_carbon":(0.,100.,10.),"Trihalomethanes":(0.,500.,60.),"Turbidity":(0.,100.,3.)}
with st.sidebar:
    st.header("Sample measurements")
    sample={k:st.number_input(k,min_value=lo,max_value=hi,value=val) for k,(lo,hi,val) in ranges.items()}
try:
    model=load_model(model_path); result=score(model,sample)
    c1,c2=st.columns([1,2])
    c1.metric("Model screening score",f"{result['screening_score']:.1%}")
    c1.write("**Priority:** "+result["screening_label"].replace("_"," ").title())
    c1.caption("Not a validated probability of contamination.")
    if report_path.exists():
        report=json.loads(report_path.read_text())
        c2.subheader("Evaluation")
        c2.write("Selected model: "+report["selected_model"])
        metrics=report["models"][report["selected_model"]]["holdout"]
        cols=c2.columns(4)
        for col,key in zip(cols,("roc_auc","f1","balanced_accuracy","recall")):
            col.metric(key.replace("_"," ").title(),f"{metrics[key]:.3f}")
        c2.subheader("Permutation feature importance")
        importance=report.get("permutation_importance",[])
        if importance: c2.bar_chart({x["feature"]:x["mean_importance"] for x in importance})
except Exception as exc:
    st.error(f"Model could not be loaded: {exc}")
