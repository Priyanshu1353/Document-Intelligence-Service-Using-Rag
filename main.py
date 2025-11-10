from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os
import tempfile
import logfire
from typing import List
from dotenv import load_dotenv

from models import ChatRequest, ChatResponse, IngestResponse, ActionExtractionResponse
from database import db
from agent import run_extraction, run_chat

load_dotenv()

# Initialize Logfire
# logfire.configure()

app = FastAPI(
    title="Document Intelligence Service",
    description="A PDF-to-Action assistant using FastAPI, FAISS, and OpenAI/Gemini.",
    version="1.1.0"
)

# Instrumentalize FastAPI with Logfire
# logfire.instrument_fastapi(app)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "document-intelligence-service"}

@app.post("/v1/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    """Uploads a PDF, extracts text, chunks it, and stores in ChromaDB."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save to a temporary file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = await db.ingest_pdf(tmp_path, file.filename)
        return IngestResponse(
            message="Document successfully ingested.",
            file_id=result["file_id"],
            chunks=result["chunks_count"]
        )
    except Exception as e:
        logfire.error("Ingestion failed: {error}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """Answers a user query based on all documents in the memory."""
    try:
        # Retrieve context from FAISS
        relevant_chunks = await db.query_db(request.query, n_results=5)
        context = "\n\n".join([r["content"] for r in relevant_chunks])
        sources = list(set([r["metadata"]["filename"] for r in relevant_chunks]))

        if not context:
            return ChatResponse(answer="I have no knowledge about this yet. Please ingest some documents first.", sources=[])

        # Generate answer using Pydantic AI agent
        answer = await run_chat(request.query, context)
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        logfire.error("Chat failed: {error}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.get("/v1/extract-actions/{file_id}", response_model=ActionExtractionResponse)
async def extract_actions_for_file(file_id: str):
    """Retrieves all text for a specific file and extracts actionable tasks."""
    try:
        # Retrieve all text for the file
        full_text = db.get_all_text_for_file(file_id)
        if not full_text:
            raise HTTPException(status_code=404, detail="File ID not found or has no content.")

        # Extract actions using Pydantic AI agent
        actions = await run_extraction(full_text)
        return ActionExtractionResponse(file_id=file_id, actions=actions)
    except Exception as e:
        logfire.error("Extraction failed: {error}", error=str(e))
        raise HTTPException(status_code=500, detail=f"Action extraction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
