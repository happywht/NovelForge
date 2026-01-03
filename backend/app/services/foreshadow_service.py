from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
from sqlmodel import Session, select
from datetime import datetime

from app.db.models import ForeshadowItem as ForeshadowItemModel


class ForeshadowService:
    def __init__(self, session: Session):
        self.session = session

    async def suggest(self, text: str, llm_config_id: int = 1) -> Dict[str, Any]:
        """
        使用 LLM 提取文本中的潜在伏笔
        """
        if not text or len(text) < 50:
            return {"goals": [], "items": [], "persons": []}

        from app.services.agent_service import run_llm_agent
        from pydantic import BaseModel

        class ForeshadowExtraction(BaseModel):
            goals: List[str]
            items: List[str]
            persons: List[str]

        user_prompt = f"请分析以下小说章节内容，提取其中埋下的伏笔线索：\n1. 角色立下的目标或誓言 (goals)\n2. 出现的特殊道具或关键物品 (items)\n3. 提及的重要未登场或神秘人物 (persons)\n\n内容：\n{text[:2000]}"
        system_prompt = "你是一个敏锐的小说评论家，擅长发现故事中的伏笔和悬念。"

        try:
            result = await run_llm_agent(
                session=self.session,
                llm_config_id=llm_config_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                output_type=ForeshadowExtraction
            )
            return result.model_dump()
        except Exception as e:
            # Fallback to empty if LLM fails
            return {"goals": [], "items": [], "persons": []}

    async def check_resolution(self, project_id: int, text: str, llm_config_id: int = 1) -> List[int]:
        """
        检查当前文本是否回收了已有的伏笔
        返回已回收的 foreshadow_item_id 列表
        """
        open_items = self.list(project_id, status='open')
        if not open_items:
            return []

        from app.services.agent_service import run_llm_agent
        from pydantic import BaseModel

        # 构造上下文
        items_desc = "\n".join([f"ID {item.id}: {item.title} ({item.note or ''})" for item in open_items])
        
        class ResolutionCheck(BaseModel):
            resolved_ids: List[int]

        user_prompt = f"以下是该小说中尚未回收的伏笔列表：\n{items_desc}\n\n请阅读最新的章节内容，判断是否有伏笔被回收或解决。如果有，请列出其ID。\n\n最新章节：\n{text[:2000]}"
        system_prompt = "你是一个细致的小说编辑，负责检查剧情线索的闭环。"

        try:
            result = await run_llm_agent(
                session=self.session,
                llm_config_id=llm_config_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                output_type=ResolutionCheck
            )
            return result.resolved_ids
        except Exception:
            return []

    # --- CRUD via DB ---
    def list(self, project_id: int, status: Optional[str] = None) -> List[ForeshadowItemModel]:
        stmt = select(ForeshadowItemModel).where(ForeshadowItemModel.project_id == project_id)
        if status:
            stmt = stmt.where(ForeshadowItemModel.status == status)
        items = self.session.exec(stmt.order_by(ForeshadowItemModel.status.desc(), ForeshadowItemModel.created_at.desc())).all()
        return items

    def register(self, project_id: int, entries: List[Dict[str, Any]]) -> List[ForeshadowItemModel]:
        out: List[ForeshadowItemModel] = []
        for it in entries:
            title = str(it.get('title') or '').strip()
            if not title:
                continue
            item = ForeshadowItemModel(
                project_id=project_id,
                chapter_id=it.get('chapter_id'),
                title=title,
                type=str(it.get('type') or 'other') or 'other',
                note=it.get('note'),
                status='open',
            )
            self.session.add(item)
            out.append(item)
        if out:
            self.session.commit()
            for i in out:
                self.session.refresh(i)
        return out

    def resolve(self, project_id: int, item_id: str | int) -> Optional[ForeshadowItemModel]:
        item = self.session.get(ForeshadowItemModel, item_id)
        if not item or item.project_id != project_id:
            return None
        if item.status != 'resolved':
            item.status = 'resolved'
            item.resolved_at = datetime.utcnow()
            self.session.add(item)
            self.session.commit()
            self.session.refresh(item)
        return item

    def delete(self, project_id: int, item_id: str | int) -> bool:
        item = self.session.get(ForeshadowItemModel, item_id)
        if not item or item.project_id != project_id:
            return False
        self.session.delete(item)
        self.session.commit()
        return True 