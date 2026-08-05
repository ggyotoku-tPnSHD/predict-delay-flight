import zipfile
import pandas as pd

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
def zip_to_parquet(zip_path, out_dir):
    with zipfile.ZipFile(zip_path) as z:
        csv_name = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(csv_name) as f:
            df = pd.read_csv(f)

