import asyncio
import httpx
import json
import os
from pathlib import Path
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000/api/deck"
OUTPUT_DIR = Path("test_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

async def test_endpoint(client: httpx.AsyncClient, endpoint: str, payload: Dict[str, Any], test_name: str, is_binary: bool = False):
    print(f"\nSTARTING Test: {test_name}")
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    start_time = time.time()
    try:
        response = await client.post(endpoint, json=payload, timeout=120.0)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            print(f"SUCCESS! (Duration: {duration:.2f}s)")
            if is_binary:
                filename = f"{test_name.lower().replace(' ', '_')}.pptx"
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(response.content)
                print(f"File saved to: {filepath}")
            else:
                result = response.json()
                filename = f"{test_name.lower().replace(' ', '_')}.json"
                filepath = OUTPUT_DIR / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"Result saved to: {filepath}")
                
                # Check for key features
                if "core" in result:
                    print(f"   Versions generated: Support({result['support']['slide_count']}), Core({result['core']['slide_count']}), Extension({result['extension']['slide_count']})")
                elif "slides" in result:
                    print(f"   Slide count: {len(result['slides'])}")
                    if len(result['slides']) > 0:
                        print(f"   Curriculum alignment check: {result.get('meta', {}).get('standards', 'N/A')}")
        else:
            print(f"FAILED: {response.status_code}")
            print(f"Detail: {response.text}")
            
    except Exception as e:
        print(f"Error during test: {str(e)}")

async def run_e2e_suite():
    print("="*60)
    print("END-TO-END TEST SUITE")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # TEST 1: Complete Pipeline (JSON)
        # We'll use a standard topic to verify RAG and Bloom's
        await test_endpoint(
            client,
            f"{BASE_URL}/generate-complete",
            {
                "topic": "Newton's Laws of Motion",
                "subject": "Physics",
                "gradeLevel": "11",
                "theme": "default"
            },
            "Complete Pipeline JSON",
            is_binary=False
        )
        
        # TEST 2: All Differentiation Levels (Parallel)
        await test_endpoint(
            client,
            f"{BASE_URL}/generate-all-levels",
            {
                "topic": "Photosynthesis",
                "subject": "Biology",
                "gradeLevel": "9",
                "theme": "science_nature"
            },
            "Differentiation Levels",
            is_binary=False
        )
        
        # TEST 3: Specific Level Generation (Support)
        await test_endpoint(
            client,
            f"{BASE_URL}/generate-level/support",
            {
                "topic": "Atomic Structure",
                "subject": "Chemistry",
                "gradeLevel": "10",
                "theme": "default"
            },
            "Support Level Generation",
            is_binary=False
        )
        
        # TEST 4: PPTX Rendering with Images (Complete PPTX)
        await test_endpoint(
            client,
            f"{BASE_URL}/generate-deck-pptx",
            {
                "topic": "Structure of a Cell",
                "subject": "Biology",
                "gradeLevel": "8",
                "theme": "science_nature"
            },
            "Complete PPTX Export",
            is_binary=True
        )

    print("\n" + "="*60)
    print("TEST SUITE FINISHED")
    print(f"Check '{OUTPUT_DIR}' for all generated files.")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_e2e_suite())
