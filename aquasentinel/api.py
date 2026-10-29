import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .predict import load_model, score

app = FastAPI(title="AquaSentinel ML API", version="0.1.0",
    description="Water-quality research screening prototype; not a safety certification.")
MODEL_PATH = os.getenv("AQUASENTINEL_MODEL", "artifacts/model.joblib")


class WaterSample(BaseModel):
    ph: float | None = Field(None, ge=0, le=14)
    Hardness: float | None = Field(None, ge=0)
    Solids: float | None = Field(None, ge=0)
    Chloramines: float | None = Field(None, ge=0)
    Sulfate: float | None = Field(None, ge=0)
    Conductivity: float | None = Field(None, ge=0)
    Organic_carbon: float | None = Field(None, ge=0)
    Trihalomethanes: float | None = Field(None, ge=0)
    Turbidity: float | None = Field(None, ge=0)


@app.get("/health")
def health():
    return {"status":"ok", "model_configured":os.path.exists(MODEL_PATH)}


@app.post("/predict")
def predict(sample: WaterSample):
    try:
        return score(load_model(MODEL_PATH), sample.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
