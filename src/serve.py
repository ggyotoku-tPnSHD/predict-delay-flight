import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from storage import download_dir
from train import FEATURES, MODEL_DIR, MODEL_PATH, ROUTES_PATH

if not MODEL_PATH.exists():
    download_dir("models", MODEL_DIR)

app = FastAPI(title="Flight Delay Predictor")
model = joblib.load(MODEL_PATH)
routes = json.loads(ROUTES_PATH.read_text())
metrics = json.loads((MODEL_DIR / "metrics.json").read_text())
INDEX_HTML = Path(__file__).parent / "static" / "index.html"

AIRLINE_NAMES = {
    "AA": "American", "AS": "Alaska", "B6": "JetBlue", "DL": "Delta", "F9": "Frontier",
    "G4": "Allegiant", "MQ": "Envoy", "NK": "Spirit", "OH": "PSA", "OO": "SkyWest",
    "UA": "United", "WN": "Southwest", "YX": "Republic",
}
airlines = list(model.named_steps["pre"].named_transformers_["cat"].categories_[0])
TIME_BLOCKS = ["0001-0559"] + [f"{h:02d}00-{h:02d}59" for h in range(6, 24)]
dests_by_origin = defaultdict(list)
for key in sorted(routes):
    origin, dest = key.split("-")
    dests_by_origin[origin].append(dest)


class FlightRequest(BaseModel):
    airline: str = Field(examples=["AA"], description="IATA carrier code")
    origin: str = Field(examples=["LAX"])
    dest: str = Field(examples=["JFK"])
    flight_date: date = Field(examples=["2026-10-15"])
    dep_time: int = Field(ge=0, le=2359, examples=[1435], description="Scheduled departure, HHMM local")


def dep_time_block(hhmm: int) -> str:
    hour = hhmm // 100
    return "0001-0559" if hour < 6 else f"{hour:02d}00-{hour:02d}59"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(INDEX_HTML)


@app.get("/meta")
def meta():
    return {
        "airlines": [{"code": c, "name": AIRLINE_NAMES.get(c, c)} for c in airlines],
        "routes": dests_by_origin,
        "model": metrics,
    }


@app.get("/health")
def health():
    return {"status": "ok", "model": metrics}


@app.post("/predict")
def predict(req: FlightRequest):
    route = f"{req.origin.upper()}-{req.dest.upper()}"
    if route not in routes:
        raise HTTPException(404, f"Unknown route {route}")
    # Score every departure block in one batch so the caller can compare times of day.
    base = {
        "Reporting_Airline": req.airline.upper(),
        "Origin": req.origin.upper(),
        "Dest": req.dest.upper(),
        "DayOfWeek": str(req.flight_date.isoweekday()),  # BTS uses 1=Mon..7=Sun
        "Distance": routes[route],
    }
    rows = pd.DataFrame([{**base, "DepTimeBlk": blk} for blk in TIME_BLOCKS])[FEATURES]
    by_block = dict(zip(TIME_BLOCKS, model.predict_proba(rows)[:, 1].round(4).tolist()))
    proba = by_block[dep_time_block(req.dep_time)]
    return {
        "route": route,
        "delay_probability": proba,
        "delayed_15min": proba >= 0.5,
        "base_rate": round(metrics["test_delay_rate"], 4),
        "by_time_block": by_block,
    }
