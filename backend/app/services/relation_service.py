from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import Session, select
from loguru import logger

from app.schemas.relation_extract import RelationExtraction, CN_TO_EN_KIND
from app.schemas.entity import Entity
from app.db.models import Card, CardType
from app.services import agent_service, prompt_service
from app.services.kg_provider import get_provider
from app.schemas.memory import ParticipantTyped

# 主宾类型约束
_ALLOWED_PAIRS: Dict[str, List[Tuple[str, str]]] = {
    '同盟': [('character','character')],
    '队友': [('character','character')],
    '同门': [('character','character')],
    '敌对': [('character','character')],
    '亲属': [('character','character')],
    '师徒': [('character','character')],
    '对手': [('character','character')],
    '伙伴': [('character','character')],
    '上级': [('character','character')],
    '下属': [('character','character')],
    '指导': [('character','character')],
    '隶属': [('character','organization')],
    '成员': [('character','organization')],
    '领导': [('character','organization'), ('organization','organization')],
    '创立': [('character','organization') , ('organization','organization')],
    '控制': [('organization','scene')],
    '位于': [('scene','organization')],
    '关于': [('character','character'), ('organization','organization'), ('character','organization'), ('organization','character')],
    '其他': [('character','character'), ('organization','organization'), ('character','organization'), ('organization','character'), ('item','item'), ('concept','concept'), ('character','concept'), ('character','item')],
}

def _guess_entity_type(session: Session, project_id: int, name: str) -> Optional[str]:
    try:
        st = select(Card).where(Card.project_id == project_id, Card.title == name)
        card = session.exec(st).first()
        if not card:
            return None
        entity = Entity.model_validate(card.content or {})
        return str(entity.entity_type)
    except Exception as e:
        logger.error(f"Error guessing entity type: {e}")
        return None

class RelationService:
    def __init__(self, session: Session):
        self.session = session
        self.graph = get_provider()

    async def extract_relations_llm(
        self, 
        text: str, 
        participants: Optional[List[ParticipantTyped]] = None, 
        llm_config_id: int = 1, 
        timeout: Optional[float] = None, 
        prompt_name: Optional[str] = "关系提取"
    ) -> RelationExtraction:
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        system_prompt = prompt.template
        
        schema_json = RelationExtraction.model_json_schema()
        system_prompt += f"\n\n请严格按照以下 JSON Schema 格式进行输出:\n{schema_json}"

        participant_names = [p.name for p in participants] if participants else []
        user_prompt = (
            f"参与者: {', '.join(participant_names)}\n\n"
            "请从以下正文中抽取：\n"
            f"{text}"
        )
        res = await agent_service.run_llm_agent(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=RelationExtraction,
            system_prompt=system_prompt,
            timeout=timeout,
        )
        if not isinstance(res, RelationExtraction):
            raise ValueError("LLM 关系抽取失败：输出格式不符合 RelationExtraction")
        return res

    def ingest_relations_from_llm(
        self, 
        project_id: int, 
        data: RelationExtraction, 
        *, 
        volume_number: Optional[int] = None, 
        chapter_number: Optional[int] = None, 
        participants_with_type: Optional[List[ParticipantTyped]] = None
    ) -> Dict[str, Any]:
        triples_with_attrs: List[tuple[str, str, str, Dict[str, Any]]] = []
        DIALOGUES_QUEUE_SIZE = 2
        EVENTS_QUEUE_SIZE = 2

        participant_type_map = {p.name: p.type for p in participants_with_type} if participants_with_type else {}

        def _merge_queue(existing: List[Any], incoming: List[Any], key_fn=lambda x: x, max_size: int = 3) -> List[Any]:
            seen = set()
            merged: List[Any] = []
            for it in (existing or []) + (incoming or []):
                try:
                    k = key_fn(it)
                    if k in seen: continue
                    seen.add(k)
                    merged.append(it)
                except Exception: continue
            return merged[-max_size:] if len(merged) > max_size else merged

        merged_evidence_map: Dict[str, Dict[str, Any]] = {}
        pairs: List[Tuple[str, str, str]] = []
        for r in (data.relations or []):
            pred = CN_TO_EN_KIND.get(r.kind or '', '')
            if pred: pairs.append((r.a, r.b, pred))

        existing_index: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        try:
            all_parts = list({p for t in pairs for p in (t[0], t[1])})
            if all_parts:
                sub = self.graph.query_subgraph(project_id=project_id, participants=all_parts, top_k=200)
                for item in (sub.get("relation_summaries") or []):
                    try:
                        a0 = item.get("a"); b0 = item.get("b"); kind_cn = item.get("kind")
                        kind_en = CN_TO_EN_KIND.get(kind_cn or '', '')
                        if not (a0 and b0 and kind_en): continue
                        existing_index[(a0, b0, kind_en)] = {
                            "recent_dialogues": item.get("recent_dialogues") or [],
                            "recent_event_summaries": item.get("recent_event_summaries") or [],
                        }
                    except Exception: continue
        except Exception: pass

        def _coerce_kind_by_types(kind_cn: str, type_a: Optional[str], type_b: Optional[str]) -> str:
            if not type_a or not type_b: return kind_cn
            allowed = _ALLOWED_PAIRS.get(kind_cn)
            if not allowed or (type_a, type_b) in allowed: return kind_cn
            return '关于'

        # 获取卡片类型映射
        card_types = self.session.exec(select(CardType).where(CardType.name.in_(['角色卡', '场景卡', '组织卡']))).all()
        type_name_to_id = {ct.name: ct.id for ct in card_types}
        
        # 实体类型到卡片类型名称的映射
        entity_to_card_type = {
            'character': '角色卡',
            'scene': '场景卡',
            'organization': '组织卡'
        }

        for r in (data.relations or []):
            pred = CN_TO_EN_KIND.get(r.kind or '', '')
            if not pred: continue
            
            type_a = participant_type_map.get(r.a) or _guess_entity_type(self.session, project_id, r.a) or 'character'
            type_b = participant_type_map.get(r.b) or _guess_entity_type(self.session, project_id, r.b) or 'character'

            # 确保卡片存在
            for name, etype in [(r.a, type_a), (r.b, type_b)]:
                st = select(Card).where(Card.project_id == project_id, Card.title == name)
                card = self.session.exec(st).first()
                if not card:
                    ct_name = entity_to_card_type.get(etype, '角色卡')
                    ct_id = type_name_to_id.get(ct_name)
                    if ct_id:
                        logger.info(f"Creating new {ct_name} for: {name}")
                        try:
                            stmt_count = select(Card).where(Card.project_id == project_id, Card.parent_id == None)
                            display_order = len(self.session.exec(stmt_count).all())
                            new_card = Card(
                                title=name,
                                project_id=project_id,
                                card_type_id=ct_id,
                                parent_id=None,
                                display_order=display_order,
                                content={"name": name, "entity_type": etype, "description": "由 AI 自动提取创建"}
                            )
                            self.session.add(new_card)
                            self.session.flush()
                        except Exception as e:
                            logger.error(f"Failed to create card for {name}: {e}")

            kind_cn_fixed = _coerce_kind_by_types(r.kind, type_a, type_b)
            pred = CN_TO_EN_KIND.get(kind_cn_fixed, pred)
            
            attributes = r.model_dump(exclude={"a", "b", "kind"}, exclude_none=True)
            if type_a != 'character' or type_b != 'character':
                attributes.pop('a_to_b_addressing', None)
                attributes.pop('b_to_a_addressing', None)
                attributes.pop('recent_dialogues', None)

            new_dialogues = [d.strip() for d in (attributes.get("recent_dialogues") or []) if isinstance(d, str) and len(d.strip()) >= 20]
            
            new_summaries: List[Dict[str, Any]] = []
            for s in (r.recent_event_summaries or []):
                try:
                    item = s.copy() if isinstance(s, dict) else s.model_dump()
                    if volume_number is not None and item.get("volume_number") is None: item["volume_number"] = int(volume_number)
                    if chapter_number is not None and item.get("chapter_number") is None: item["chapter_number"] = int(chapter_number)
                    if str(item.get("summary") or "").strip(): new_summaries.append(item)
                except Exception: continue

            key = (r.a, r.b, pred)
            prev = existing_index.get(key, {})
            merged_dialogues = _merge_queue(list(prev.get("recent_dialogues") or []), new_dialogues, max_size=DIALOGUES_QUEUE_SIZE)
            merged_summaries = _merge_queue(list(prev.get("recent_event_summaries") or []), new_summaries, key_fn=lambda x: (x.get("summary") if isinstance(x, dict) else ""), max_size=EVENTS_QUEUE_SIZE)

            if merged_dialogues: attributes["recent_dialogues"] = merged_dialogues
            else: attributes.pop("recent_dialogues", None)
            if merged_summaries: attributes["recent_event_summaries"] = merged_summaries
            else: attributes.pop("recent_event_summaries", None)
            
            triples_with_attrs.append((r.a, pred, r.b, attributes))
            merged_evidence_map[str(key)] = {
                "recent_dialogues": attributes.get("recent_dialogues", []),
                "recent_event_summaries": [s.get('summary') for s in attributes.get("recent_event_summaries", [])]
            }
        
        self.session.commit()

        if triples_with_attrs:
            try:
                self.graph.ingest_triples_with_attributes(project_id, triples_with_attrs)
            except Exception as e:
                raise ValueError(f"知识图谱写入失败: {e}")
        
        return {"written": len(triples_with_attrs), "merged_evidence": merged_evidence_map}
