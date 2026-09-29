import zipfile
import logging
from pathlib import Path

import pandas as pd

from logging_config import setup_logging
from storage import upload_dir

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
PARQUET_DIR = DATA_DIR / "parquet"

COLUMNS = [
    "FlightDate", "Year", "Month", "DayofMonth", "DayOfWeek",
    "Reporting_Airline", "Tail_Number", "Flight_Number_Reporting_Airline",
    "Origin", "OriginState", "Dest", "DestState",
    "CRSDepTime", "CRSArrTime", "CRSElapsedTime",
    "DepTimeBlk", "ArrTimeBlk",
    "Distance", "DistanceGroup",
    "ArrDel15", "ArrDelay",
    "Cancelled", "Diverted",
]


def zip_to_parquet(zip_path: Path, out_dir: Path = PARQUET_DIR) -> int:
    with zipfile.ZipFile(zip_path) as z:
        csv_name = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(csv_name) as f:
            df = pd.read_csv(f, usecols=COLUMNS)

    rows_read = len(df)
    # Cancelled/diverted flights have no arrival delay, so they can't be labeled.
    df = df[~df["Cancelled"].astype(bool) & ~df["Diverted"].astype(bool)]
    df = df.drop(columns=["Diverted", "Cancelled"])
    df = df.dropna(subset=["ArrDel15"])
    df["ArrDel15"] = df["ArrDel15"].astype("int8")

    # delete_matching overwrites this month's partition, so reruns don't duplicate rows.
    df.to_parquet(
        out_dir, engine="pyarrow", partition_cols=["Year", "Month"], index=False,
        existing_data_behavior="delete_matching",
    )
    log.info(
        "transform %s rows_read=%d rows_kept=%d dropped=%d",
        zip_path.name, rows_read, len(df), rows_read - len(df),
    )
    return len(df)


if __name__ == "__main__":
    setup_logging("transform")
    for zip_path in sorted(DATA_DIR.glob("On_time_*.zip")):
        zip_to_parquet(zip_path)
    # Months already in S3 are skipped, so reruns only upload new data.
    for part in sorted(PARQUET_DIR.glob("Year=*/Month=*")):
        upload_dir(part, f"parquet/{part.relative_to(PARQUET_DIR).as_posix()}")
