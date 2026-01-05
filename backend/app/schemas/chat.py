from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

class ChatSessionRead(BaseModel):
    id: int
    project_id: int
    character_card_id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

class ChatSessionCreate(BaseModel):
    project_id: int
    character_card_id: int
    title: Optional[str] = "New Chat"

class ChatMessageCreate(BaseModel):
    content: str
    llm_config_id: Optional[int] = None
