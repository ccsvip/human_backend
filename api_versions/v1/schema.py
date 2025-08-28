from pydantic import BaseModel
from typing import Optional


class ChatMessageSchema(BaseModel):
    text: str


class Text2SpeechSchema(BaseModel):
    text: str
    model: Optional[str] = ''


class ProcessTextTSchema(BaseModel):
    text: str
    reference_id: str
    user_id: str