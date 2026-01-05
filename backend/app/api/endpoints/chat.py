from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.db.session import get_session
from app.services.character_chat_service import CharacterChatService
from app.schemas.chat import ChatSessionRead, ChatSessionCreate, ChatMessageRead, ChatMessageCreate

router = APIRouter()

@router.post("/sessions", response_model=ChatSessionRead)
def create_session(
    session_in: ChatSessionCreate,
    db: Session = Depends(get_session)
):
    service = CharacterChatService(db)
    return service.create_session(
        project_id=session_in.project_id,
        character_card_id=session_in.character_card_id,
        title=session_in.title
    )

@router.get("/sessions", response_model=List[ChatSessionRead])
def list_sessions(
    project_id: int,
    db: Session = Depends(get_session)
):
    service = CharacterChatService(db)
    return service.get_project_sessions(project_id)

@router.get("/sessions/{session_id}", response_model=ChatSessionRead)
def get_session_details(
    session_id: int,
    db: Session = Depends(get_session)
):
    service = CharacterChatService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageRead])
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_session)
):
    service = CharacterChatService(db)
    return service.get_history(session_id)

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageRead)
async def send_message(
    session_id: int,
    message_in: ChatMessageCreate,
    db: Session = Depends(get_session)
):
    service = CharacterChatService(db)
    try:
        return await service.send_message(
            session_id=session_id,
            user_content=message_in.content,
            llm_config_id=message_in.llm_config_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
