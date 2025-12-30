from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlmodel import Session

from app.schemas.relation_extract import RelationExtraction
from app.schemas.entity import UpdateDynamicInfo
from app.schemas.memory import ParticipantTyped

from app.services.kg_provider import get_provider
from app.services.dynamic_info_service import DynamicInfoService
from app.services.relation_service import RelationService

class MemoryService:
    def __init__(self, session: Session):
        self.session = session
        self.graph = get_provider()
        self.dynamic_info_svc = DynamicInfoService(session)
        self.relation_svc = RelationService(session)

    async def extract_relations_llm(self, text: str, participants: Optional[List[ParticipantTyped]] = None, llm_config_id: int = 1, timeout: Optional[float] = None, prompt_name: Optional[str] = "关系提取") -> RelationExtraction:
        return await self.relation_svc.extract_relations_llm(text, participants, llm_config_id, timeout, prompt_name)

    async def extract_dynamic_info_from_text(self, text: str, participants: Optional[List[ParticipantTyped]] = None, llm_config_id: int = 1, timeout: Optional[float] = None, prompt_name: Optional[str] = "角色动态信息提取", project_id: Optional[int] = None, extra_context: Optional[str] = None) -> UpdateDynamicInfo:
        return await self.dynamic_info_svc.extract_dynamic_info_from_text(text, participants, llm_config_id, timeout, prompt_name, project_id, extra_context)

    def query_subgraph(
        self,
        project_id: int,
        participants: Optional[List[str]] = None,
        radius: int = 2,
        edge_type_whitelist: Optional[List[str]] = None,
        top_k: int = 50,
        max_chapter_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.graph.query_subgraph(
            project_id=project_id,
            participants=participants,
            radius=radius,
            edge_type_whitelist=edge_type_whitelist,
            top_k=top_k,
            max_chapter_id=max_chapter_id,
        )

    def ingest_relations_from_llm(self, project_id: int, data: RelationExtraction, *, volume_number: Optional[int] = None, chapter_number: Optional[int] = None, participants_with_type: Optional[List[ParticipantTyped]] = None) -> Dict[str, Any]:
        return self.relation_svc.ingest_relations_from_llm(project_id, data, volume_number=volume_number, chapter_number=chapter_number, participants_with_type=participants_with_type)

    def update_dynamic_character_info(self, project_id: int, data: UpdateDynamicInfo, queue_size: int = 3) -> Dict[str, Any]:
        return self.dynamic_info_svc.update_dynamic_character_info(project_id, data, queue_size=queue_size)