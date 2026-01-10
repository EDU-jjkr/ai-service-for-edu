import asyncio
import httpx
import json
import time

async def test_single():
    url = "http://127.0.0.1:8000/api/deck/generate-complete"
    payload = {
        "topic": "Gravity",
        "subject": "Physics",
        "gradeLevel": "9"
    }
    
    print(f"Testing {url}...")
    async with httpx.AsyncClient() as client:
        try:
            start = time.time()
            response = await client.post(url, json=payload, timeout=60.0)
            print(f"Status: {response.status_code}")
            print(f"Time: {time.time() - start:.2f}s")
            if response.status_code == 200:
                print("Success!")
                print(json.dumps(response.json(), indent=2)[:500] + "...")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_single())
