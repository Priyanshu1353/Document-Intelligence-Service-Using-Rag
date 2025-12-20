import asyncio
import os
import requests
import json
from database import db
from agent import run_chat, run_extraction

# Mocking data for test
SAMPLE_PDF = "sample_test.pdf"

async def test_database_logic():
    print("\n--- Testing Database Logic ---")
    if not os.path.exists(SAMPLE_PDF):
        print(f"Error: {SAMPLE_PDF} not found. Run create_sample_pdf.py first.")
        return

    # test ingestion
    print("[*] Testing PDF ingestion...")
    result = await db.ingest_pdf(SAMPLE_PDF, "sample_test.pdf")
    file_id = result["file_id"]
    print(f"Success: {result['chunks_count']} chunks ingested. File ID: {file_id}")

    # test query
    print("[*] Testing similarity search...")
    query = "When is the project kick-off meeting?"
    results = await db.query_db(query, n_results=2)
    print(f"Found {len(results)} relevant chunks.")
    for i, res in enumerate(results):
         print(f"Chunk {i+1}: {res['content'][:100]}...")

    # test full text retrieval
    print("[*] Testing full text retrieval for extraction...")
    full_text = db.get_all_text_for_file(file_id)
    print(f"Retrieved {len(full_text)} characters.")
    
    return file_id, full_text

async def test_agent_logic(file_id, full_text):
    print("\n--- Testing Agent Logic ---")
    
    # test chat
    print("[*] Testing chat with Gemini...")
    query = "What is the budget for the first phase?"
    context = full_text[:2000] # Use top text as context
    answer = await run_chat(query, context)
    print(f"Question: {query}")
    print(f"Answer: {answer}")

    # test extraction
    print("[*] Testing extraction with Gemini...")
    actions = await run_extraction(full_text)
    print(f"Extracted {len(actions)} actionable items.")
    for action in actions:
        print(f"- [{action.category}] {action.description} (Date: {action.due_date}, Amount: {action.amount})")

async def test_api_endpoints():
    print("\n--- Testing API Endpoints ---")
    API_URL = "http://127.0.0.1:8000"
    
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code == 200:
             print("Health check: PASS")
        else:
             print(f"Health check: FAIL ({response.status_code})")
             return
    except Exception:
        print("API is not running. Skip API tests.")
        return

    # Test ingestion endpoint
    print("[*] Testing /v1/ingest...")
    with open(SAMPLE_PDF, "rb") as f:
         files = {"file": (SAMPLE_PDF, f, "application/pdf")}
         response = requests.post(f"{API_URL}/v1/ingest", files=files)
         if response.status_code == 200:
             data = response.json()
             file_id = data["file_id"]
             print(f"Ingest: PASS (ID: {file_id})")
         else:
             print(f"Ingest: FAIL ({response.status_code}: {response.text})")
             return

    # Test chat endpoint
    print("[*] Testing /v1/chat...")
    response = requests.post(f"{API_URL}/v1/chat", json={"query": "What is the contact email?"})
    if response.status_code == 200:
        data = response.json()
        print(f"Chat: PASS (Answer: {data['answer']})")
    else:
        print(f"Chat: FAIL ({response.status_code})")

    # Test extraction endpoint
    print("[*] Testing /v1/extract-actions...")
    response = requests.get(f"{API_URL}/v1/extract-actions/{file_id}")
    if response.status_code == 200:
        data = response.json()
        print(f"Extraction: PASS ({len(data['actions'])} items)")
    else:
        print(f"Extraction: FAIL ({response.status_code})")

async def main():
    file_id, full_text = await test_database_logic()
    if file_id and full_text:
        await test_agent_logic(file_id, full_text)
    
    # We test API separately as it needs the server running
    await test_api_endpoints()

if __name__ == "__main__":
    asyncio.run(main())
