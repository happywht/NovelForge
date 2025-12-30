from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlmodel import Session, select
from loguru import logger

from app.schemas.entity import UpdateDynamicInfo, CharacterCard, Entity
from app.db.models import Card
from app.services import agent_service, prompt_service

# 动态信息每类别数量上限
DYNAMIC_INFO_LIMITS: Dict[str, int] = {
    "系统/模拟器/金手指信息": 3,
    "等级/修为境界": 3,
    "装备/法宝": 3,
    "知识/情报": 3,
    "资产/领地": 3,
    "功法/技能": 3,
    "血脉/体质": 3,
    "心理想法/目标快照": 3,
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

class DynamicInfoService:
    def __init__(self, session: Session):
        self.session = session

    async def extract_dynamic_info_from_text(
        self, 
        text: str, 
        participants: Optional[List[Any]] = None, 
        llm_config_id: int = 1, 
        timeout: Optional[float] = None, 
        prompt_name: Optional[str] = "角色动态信息提取", 
        project_id: Optional[int] = None, 
        extra_context: Optional[str] = None
    ) -> UpdateDynamicInfo:
        prompt = prompt_service.get_prompt_by_name(self.session, prompt_name)
        if not prompt:
            raise ValueError(f"未找到提示词: {prompt_name}")
        system_prompt = prompt.template

        schema_json = UpdateDynamicInfo.model_json_schema()
        system_prompt += f"\n\n请严格按照以下 JSON Schema 格式进行输出:\n{schema_json}"

        ref_blocks: List[str] = []
        if extra_context:
            ref_blocks.append(f"【大纲参考信息，不允许从中提取信息】\n{extra_context}")

        character_participants = [p for p in (participants or []) if getattr(p, 'type', None) == 'character']
        if project_id and character_participants:
            try:
                lines: List[str] = []
                for p in character_participants:
                    st = select(Card).where(Card.project_id == project_id, Card.title == p.name)
                    card = self.session.exec(st).first()
                    if not card or not card.card_type or card.card_type.name != '角色卡':
                        continue
                    try:
                        model = CharacterCard.model_validate(card.content or {})
                        di = model.dynamic_info or {}
                        if not di:
                            continue
                        lines.append(f"- {p.name}:")
                        for cat_enum, items in di.items():
                            if not items:
                                continue
                            preview = "; ".join([f"[{it.id}] {it.info}" for it in items[:5]])
                            limit = DYNAMIC_INFO_LIMITS.get(cat_enum, 3)
                            info_line = f"  • {cat_enum} ({len(items)}/{limit}): {preview}"
                            lines.append(info_line)
                    except Exception as e:
                        logger.error(f"Error preparing dynamic info context: {e}")
                        continue
                if lines:
                    ref_blocks.append("【现有角色动态信息（只读参考）】\n" + "\n".join(lines))
            except Exception as e:
                logger.error(f"Error preparing dynamic info context: {e}")

        ref_text = ("\n\n".join(ref_blocks) + "\n\n") if ref_blocks else ""

        user_prompt = (
            f"{ref_text}"
            f"章节正文：\n"
            f"{text}"
            f"请为以下参与者抽取动态信息：\n"
            f"{', '.join([p.name for p in character_participants])}\n\n"
        )

        res = await agent_service.run_llm_agent(
            session=self.session,
            llm_config_id=llm_config_id,
            user_prompt=user_prompt,
            output_type=UpdateDynamicInfo,
            system_prompt=system_prompt,
            timeout=timeout,
        )

        if not isinstance(res, UpdateDynamicInfo):
            raise ValueError("LLM 动态信息抽取失败：输出格式不符合 UpdateDynamicInfo")
        
        if character_participants:
            name_set = {p.name for p in character_participants}
            if isinstance(res.info_list, list):
                res.info_list = [it for it in res.info_list if (it.name or '').strip() in name_set]
        
        return res

    def update_dynamic_character_info(self, project_id: int, data: UpdateDynamicInfo, queue_size: int = 3) -> Dict[str, Any]:
        if data.delete_info_list:
            for del_item in data.delete_info_list:
                if str(del_item.dynamic_type) == '心理想法/目标快照':
                    continue
                st = select(Card).where(Card.project_id == project_id, Card.title == del_item.name)
                card = self.session.exec(st).first()
                if not card or card.card_type.name != '角色卡':
                    continue
                
                try:
                    model = CharacterCard.model_validate(card.content or {})
                    if model.dynamic_info and del_item.dynamic_type in model.dynamic_info:
                        model.dynamic_info[del_item.dynamic_type] = [
                            item for item in model.dynamic_info[del_item.dynamic_type] if item.id != del_item.id
                        ]
                        card.content = model.model_dump(exclude_unset=True)
                        self.session.add(card)
                except Exception as e:
                    logger.warning(f"Failed to process deletion for {del_item.name}: {e}")
            self.session.commit()

        updated_cards: Dict[str, Card] = {}
        all_names = list(set([i.name for i in data.info_list]))
        if not all_names:
            return {"success": False, "updated_card_count": 0}

        stmt = select(Card).where(Card.project_id == project_id, Card.title.in_(all_names))
        cards = self.session.exec(stmt).all()
        card_map = {c.title: c for c in cards if c.card_type and c.card_type.name == '角色卡'}

        for info_group in data.info_list:
            card = updated_cards.get(info_group.name) or card_map.get(info_group.name)
            if not card:
                continue

            try:
                model = CharacterCard.model_validate(card.content or {})
                if not model.dynamic_info:
                    model.dynamic_info = {}

                for cat, items in info_group.dynamic_info.items():
                    if not items:
                        continue
                    
                    if cat not in model.dynamic_info:
                        model.dynamic_info[cat] = []
                    
                    existing_items = model.dynamic_info[cat]
                    
                    for new_item in items:
                        if not isinstance(new_item.id, int) or new_item.id <= 0:
                            new_item.id = 0
                        existing_items.append(new_item)
                    
                    existing_positive = [it.id for it in existing_items if isinstance(it.id, int) and it.id > 0]
                    next_id = (max(existing_positive) + 1) if existing_positive else 1
                    for it in existing_items:
                        if not isinstance(it.id, int) or it.id <= 0:
                            it.id = next_id
                            next_id += 1
                    
                    limit = DYNAMIC_INFO_LIMITS.get(cat, queue_size)
                    if str(cat) == '心理想法/目标快照':
                        model.dynamic_info[cat] = existing_items[-limit:]
                    else:
                        model.dynamic_info[cat] = existing_items[:limit]

                card.content = model.model_dump(exclude_unset=True)
                updated_cards[card.title] = card
            except Exception as e:
                logger.warning(f"Failed to process addition for {info_group.name}: {e}")

        for card in updated_cards.values():
            self.session.add(card)
        
        if updated_cards:
            self.session.commit()
            for card in updated_cards.values():
                self.session.refresh(card)

        return {"success": True, "updated_card_count": len(updated_cards)}
