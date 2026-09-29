import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from logging_config import setup_logging
from storage import upload_dir
from transform import PARQUET_DIR

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "model.joblib"
ROUTES_PATH = MODEL_DIR / "routes.json"

CATEGORICAL = ["Reporting_Airline", "Origin", "Dest", "DepTimeBlk", "DayOfWeek"]
NUMERIC = ["Distance"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "ArrDel15"


def build_pipeline() -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=1000))])


def train(test_month: int = 3) -> dict:
    df = pd.read_parquet(PARQUET_DIR, columns=FEATURES + [TARGET, "Month"])
    df["DayOfWeek"] = df["DayOfWeek"].astype(str)
    df["Month"] = df["Month"].astype(int)
    # Time-based split: train on earlier months, evaluate on the latest one.
    train_df = df[df["Month"] < test_month]
    test_df = df[df["Month"] == test_month]

    model = build_pipeline().fit(train_df[FEATURES], train_df[TARGET])
    proba = model.predict_proba(test_df[FEATURES])[:, 1]

    metrics = {
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "test_month": test_month,
        "test_delay_rate": float(test_df[TARGET].mean()),
        "test_auc": float(roc_auc_score(test_df[TARGET], proba)),
    }
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    # Distance is fixed per route, so serving can look it up instead of asking the caller.
    routes = df.groupby(["Origin", "Dest"])["Distance"].first()
    ROUTES_PATH.write_text(json.dumps({f"{o}-{d}": v for (o, d), v in routes.items()}))
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    upload_dir(MODEL_DIR, "models", overwrite=True)
    log.info("train %s", metrics)
    return metrics


if __name__ == "__main__":
    setup_logging("train")
    train()
