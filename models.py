from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ActionableItem(BaseModel):
    """Structured data for an action item extracted from a document."""
    title: str = Field(..., description="A short, descriptive title of the action item")
    date_detected: str = Field(..., description="ISO 8601 formatted date/time when this action was detected or is due")
    amount: Optional[float] = Field(None, description="Monetary amount associated with the action, if any")
    category: str = Field(..., description="Category of the action: Payment, Deadline, Meeting, or Task")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[str]

class IngestResponse(BaseModel):
    message: str
    file_id: str
    chunks: int

class ActionExtractionResponse(BaseModel):
    file_id: str
    actions: List[ActionableItem]
