from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CropConfig(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ChatMessage(BaseModel):
    timestamp_seconds: float
    champion: Optional[str] = None
    sender_raw: str
    chat: str
    confidence: float
    raw_ocr: str


class ParseOutput(BaseModel):
    source_video: str
    crop: CropConfig
    messages: List[ChatMessage] = Field(default_factory=list)
