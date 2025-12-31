import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
from typing import List
from models import ActionableItem

load_dotenv()

# Configure Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY and "your_key_here" not in API_KEY:
    genai.configure(api_key=API_KEY)

MODEL_NAME = os.getenv("LLM_MODEL", "gemini-2.5-flash")

def run_extraction(text: str) -> List[ActionableItem]:
    """Runs data extraction using Gemini with structured output (synchronous)."""
    if not API_KEY or "your_key_here" in API_KEY:
        return []

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=(
            "You are an expert document analysis assistant. "
            "Extract all actionable items from the provided text, such as deadlines, payments, meetings, and specific tasks. "
            "Ensure dates are in ISO 8601 format. If an amount is mentioned, extract it. "
            "Categorize each item as 'Payment', 'Deadline', 'Meeting', or 'Task'. "
            "Return the result as a JSON list of objects matching the ActionableItem schema."
        )
    )

    response = model.generate_content(
        f"Analyze this text and return ONLY the JSON list:\n\n{text[:20000]}",
        generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
    )

    try:
        data = json.loads(response.text)
        if isinstance(data, dict):
            # Sometimes Gemini wraps in a top level key
            for val in data.values():
                if isinstance(val, list):
                    return [ActionableItem(**item) for item in val]
        return [ActionableItem(**item) for item in data]
    except Exception as e:
        print(f"Error parsing Gemini extraction: {e}")
        return []

def run_chat(query: str, context: str) -> str:
    """Answers query based on provided context using Gemini (synchronous)."""
    if not API_KEY or "your_key_here" in API_KEY:
        return "Please set GEMINI_API_KEY in the .env file."

    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer the question using ONLY the context above."
    
    response = model.generate_content(prompt)
    return response.text
