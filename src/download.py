import httpx
import asyncio
import aiofiles
from pathlib import Path 

DATA_DIR = Path(__file__).parent.parent / "data"

async def download_bts_data_async(client:httpx.AsyncClient, year:int, month:int, save_dir=DATA_DIR):

    save_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
    filename = f"On_time_{year}_{month:02d}.zip"
    filepath = save_dir / filename
    
    print(f"Starting: {filepath}")    

    async with client.stream("GET", url) as response:
        response.raise_for_status()
        expected = int(response.headers.get("content-length",0)) 
        written = 0

        async with aiofiles.open(filepath, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=8192):
                await f.write(chunk)
                written += len(chunk)
        
    if expected and written != expected:
        raise IOError(f"Truncated: {written}/{expected} bytes")

    print(f"Finished: {filename}")

    return filepath



