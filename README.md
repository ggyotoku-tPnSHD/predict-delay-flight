# Flight Delay Predictor

Predicts the chance a US domestic flight arrives 15+ minutes late, from 1.6M flights of Bureau of Transportation Statistics (BTS) on-time data.

**Live demo:** https://flight-delay-q0tu.onrender.com (free tier: the first load after idle takes ~30–50 s)

## Pipeline

```
BTS monthly zips ──> download.py ──> transform.py ──> S3 (parquet/Year=/Month=/)
                     async httpx     clean, filter,        │
                                     partitioned parquet   ▼
                                                        train.py ──> S3 (models/)
                                                                        │
                                                                        ▼
                                                  serve.py (FastAPI) + web demo
```

| Stage | What it does |
|---|---|
| `download.py` | Streams monthly BTS PREZIP archives concurrently and checks for truncated downloads. |
| `transform.py` | Keeps the prediction columns, drops cancelled and diverted flights (they have no arrival delay), writes Parquet partitioned by year and month. Reruns overwrite a month instead of duplicating it. |
| `storage.py` | Uploads partitions to S3, skipping months already there, and syncs model artifacts. |
| `train.py` | Logistic regression on airline, origin, destination, departure hour, day of week and distance. |
| `serve.py` | FastAPI service. Loads the model from S3 at startup and serves the demo page. |

## Model

Evaluated on a held-out future month: trained on January–February 2026 (1.02M flights), tested on March 2026 (592K flights).

| Metric | Value |
|---|---|
| Test AUC | 0.638 |
| Delay rate (test month) | 24.3% |

This is a baseline. Next steps: weather and airport-congestion features, and drift monitoring that triggers retraining as new months arrive.

## API

| Endpoint | Description |
|---|---|
| `POST /predict` | `{"airline": "AA", "origin": "LAX", "dest": "JFK", "flight_date": "2026-10-16", "dep_time": 1835}` → delay probability plus the probability for every departure hour on that route |
| `GET /meta` | Airlines and routes the model knows |
| `GET /health` | Status and model metrics |
| `GET /docs` | Interactive API docs |

## Run locally

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cd src
python main.py        # download Jan–Mar 2026
python transform.py   # zip -> parquet, upload to S3
python train.py       # train, upload model to S3
uvicorn serve:app     # http://localhost:8000
```

S3 access uses standard AWS credentials; the bucket and region come from `PIPELINE_BUCKET` and `PIPELINE_REGION`.
