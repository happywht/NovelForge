from typing import List, Optional
from sqlmodel import Session, select
from app.db.models import AIGenerationHistory
from datetime import datetime

def save_history(
    session: Session,
    project_id: int,
    card_id: Optional[int],
    prompt_name: str,
    content: str,
    llm_config_id: Optional[int] = None,
    meta_data: Optional[dict] = None
) -> AIGenerationHistory:
    """保存 AI 生成历史记录"""
    history = AIGenerationHistory(
        project_id=project_id,
        card_id=card_id,
        prompt_name=prompt_name,
        content=content,
        llm_config_id=llm_config_id,
        meta_data=meta_data,
        created_at=datetime.utcnow()
    )
    session.add(history)
    session.commit()
    session.refresh(history)
    return history

def get_history_by_card(session: Session, card_id: int, limit: int = 50) -> List[AIGenerationHistory]:
    """获取指定卡片的生成历史列表"""
    statement = (
        select(AIGenerationHistory)
        .where(AIGenerationHistory.card_id == card_id)
        .order_by(AIGenerationHistory.created_at.desc())
        .limit(limit)
    )
    return session.exec(statement).all()

def get_history_by_project(session: Session, project_id: int, limit: int = 50) -> List[AIGenerationHistory]:
    """获取指定项目的生成历史列表"""
    statement = (
        select(AIGenerationHistory)
        .where(AIGenerationHistory.project_id == project_id)
        .order_by(AIGenerationHistory.created_at.desc())
        .limit(limit)
    )
    return session.exec(statement).all()

def get_history_by_id(session: Session, history_id: int) -> Optional[AIGenerationHistory]:
    """获取单条历史记录详情"""
    return session.get(AIGenerationHistory, history_id)

def delete_history(session: Session, history_id: int) -> bool:
    """删除单条历史记录"""
    history = session.get(AIGenerationHistory, history_id)
    if history:
        session.delete(history)
        session.commit()
        return True
    return False
