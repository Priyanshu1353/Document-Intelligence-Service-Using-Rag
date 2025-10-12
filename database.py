import faiss
import numpy as np
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
import os
import uuid
import pickle
import google.generativeai as genai
from typing import List, Dict, Any
from dotenv import load_dotenv
import asyncio
import time

load_dotenv()

# Configuration
STORAGE_PATH = "faiss_store"
METADATA_FILE = os.path.join(STORAGE_PATH, "metadata.pkl")
INDEX_FILE = os.path.join(STORAGE_PATH, "index.faiss")

# Configure Gemini (for Chat only now)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and "your_key_here" not in GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class DocumentDB:
    def __init__(self, dimension: int = 384):  # Default for all-MiniLM-L6-v2
        self.dimension = dimension
        if not os.path.exists(STORAGE_PATH):
            os.makedirs(STORAGE_PATH)
        
        # Initialize local embeddings model
        print("[*] Loading HuggingFace embeddings model (all-MiniLM-L6-v2)...")
        self.embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        if os.path.exists(INDEX_FILE):
            try:
                self.index = faiss.read_index(INDEX_FILE)
                # Verify dimension
                if self.index.d != dimension:
                    print(f"[!] Dimension mismatch ({self.index.d} != {dimension}). Recreating index.")
                    self.index = faiss.IndexFlatIP(dimension)
                    self.metadata_store = {}
                else:
                    with open(METADATA_FILE, "rb") as f:
                        self.metadata_store = pickle.load(f)
            except Exception as e:
                print(f"[!] Error loading index: {e}. Recreating.")
                self.index = faiss.IndexFlatIP(dimension)
                self.metadata_store = {}
        else:
            self.index = faiss.IndexFlatIP(dimension)
            self.metadata_store = {}

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", " ", ""]
        )

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Fetch embedding from local HuggingFace model."""
        # Run in thread pool because it's CPU intensive
        vector = await asyncio.to_thread(self.embeddings_model.embed_query, text)
        embedding = np.array(vector, dtype='float32')
        faiss.normalize_L2(embedding.reshape(1, -1))
        return embedding

    async def _get_batch_embeddings(self, texts: List[str]) -> np.ndarray:
        """Fetch multiple embeddings from local HuggingFace model."""
        vectors = await asyncio.to_thread(self.embeddings_model.embed_documents, texts)
        embeddings = np.array(vectors, dtype='float32')
        for i in range(len(embeddings)):
            faiss.normalize_L2(embeddings[i].reshape(1, -1))
        return embeddings

    async def ingest_pdf(self, file_path: str, filename: str, batch_size: int = 32) -> Dict[str, Any]:
        """Extracts text from PDF, chunks it, and stores in FAISS using local embeddings."""
        start_time = time.time()
        print(f"[*] Starting local ingestion for {filename}...")
        
        doc = fitz.open(file_path)
        file_id = str(uuid.uuid4())
        
        # 1. Collect all chunks and metadata
        all_chunks_data = []
        for page_num, page in enumerate(doc):
            text = page.get_text()
            page_chunks = self.text_splitter.split_text(text)
            for i, chunk in enumerate(page_chunks):
                all_chunks_data.append({
                    "content": chunk,
                    "metadata": {
                        "filename": filename,
                        "file_id": file_id,
                        "page_number": page_num + 1,
                        "chunk_index": i
                    }
                })
        
        if not all_chunks_data:
            doc.close()
            return {"file_id": file_id, "chunks_count": 0}

        # 2. Process in batches
        batches = [all_chunks_data[i : i + batch_size] for i in range(0, len(all_chunks_data), batch_size)]
        
        for i, batch in enumerate(batches):
            batch_texts = [item["content"] for item in batch]
            try:
                embeddings = await self._get_batch_embeddings(batch_texts)
                start_idx = self.index.ntotal
                self.index.add(embeddings)
                for j, item in enumerate(batch):
                    self.metadata_store[start_idx + j] = item
                
                if i % 5 == 0:
                    print(f"    [Progress] Processed {i+1}/{len(batches)} batches...")
            except Exception as e:
                print(f"    [Error] batch {i}: {e}")

        self._save()
        total_time = time.time() - start_time
        print(f"[!] TOTAL INGESTION TIME (Local): {total_time:.2f}s.")
        
        doc.close()
        return {"file_id": file_id, "chunks_count": len(all_chunks_data)}

    async def query_db(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Performs a similarity search in FAISS."""
        query_embedding = await self._get_embedding(query)
        distances, indices = self.index.search(query_embedding.reshape(1, -1), n_results)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx in self.metadata_store:
                results.append(self.metadata_store[idx])
        return results

    def get_all_text_for_file(self, file_id: str) -> str:
        """Retrieves all text chunks for a specific file_id."""
        file_chunks = []
        for idx, item in self.metadata_store.items():
            if item.get("metadata", {}).get("file_id") == file_id:
                file_chunks.append(item)
                
        file_chunks.sort(key=lambda x: (x["metadata"]["page_number"], x["metadata"]["chunk_index"]))
        return "\n".join([c["content"] for c in file_chunks])

    def _save(self):
        faiss.write_index(self.index, INDEX_FILE)
        with open(METADATA_FILE, "wb") as f:
            pickle.dump(self.metadata_store, f)

# Singleton instance
db = DocumentDB(dimension=384)
