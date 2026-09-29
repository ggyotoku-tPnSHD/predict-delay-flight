import json
from datetime import date

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from storage import download_dir
from train import FEATURES, MODEL_DIR, MODEL_PATH, ROUTES_PATH

if not MODEL_PATH.exists():
    download_dir("models", MODEL_DIR)

app = FastAPI(title="Flight Delay Predictor")
model = joblib.load(MODEL_PATH)
routes = json.loads(ROUTES_PATH.read_text())
metrics = json.loads((MODEL_DIR / "metrics.json").read_text())


class FlightRequest(BaseModel):
    airline: str = Field(examples=["AA"], description="IATA carrier code")
    origin: str = Field(examples=["LAX"])
    dest: str = Field(examples=["JFK"])
    flight_date: date = Field(examples=["2026-10-15"])
    dep_time: int = Field(ge=0, le=2359, examples=[1435], description="Scheduled departure, HHMM local")


def dep_time_block(hhmm: int) -> str:
    hour = hhmm // 100
    return "0001-0559" if hour < 6 else f"{hour:02d}00-{hour:02d}59"


@app.get("/health")
def health():
    return {"status": "ok", "model": metrics}


@app.post("/predict")
def predict(req: FlightRequest):
    route = f"{req.origin.upper()}-{req.dest.upper()}"
    if route not in routes:
        raise HTTPException(404, f"Unknown route {route}")
    row = pd.DataFrame([{
        "Reporting_Airline": req.airline.upper(),
        "Origin": req.origin.upper(),
        "Dest": req.dest.upper(),
        "DepTimeBlk": dep_time_block(req.dep_time),
        "DayOfWeek": str(req.flight_date.isoweekday()),  # BTS uses 1=Mon..7=Sun
        "Distance": routes[route],
    }])[FEATURES]
    proba = float(model.predict_proba(row)[0, 1])
    return {"route": route, "delay_probability": round(proba, 4), "delayed_15min": proba >= 0.5}
