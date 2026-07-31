import asyncio
import httpx
from download import download_bts_data_async

async def main():
   async with httpx.AsyncClient(timeout=120.0) as client:   
        months = [1,2,3]
        tasks = [download_bts_data_async(client, 2026, m) for m in months]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f"All downloads complete: {results}")    

if __name__ == "__main__":
    asyncio.run(main())
