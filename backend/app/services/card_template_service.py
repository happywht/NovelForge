from typing import List, Optional
from sqlmodel import Session, select
from app.db.models import CardTemplate, CardType
from app.schemas.card import CardTemplateCreate, CardTemplateUpdate


class CardTemplateService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[CardTemplate]:
        return self.db.exec(select(CardTemplate)).all()

    def get_by_id(self, template_id: int) -> Optional[CardTemplate]:
        return self.db.get(CardTemplate, template_id)

    def get_by_card_type(self, card_type_id: int) -> List[CardTemplate]:
        statement = select(CardTemplate).where(CardTemplate.card_type_id == card_type_id)
        return self.db.exec(statement).all()

    def create(self, template_create: CardTemplateCreate) -> CardTemplate:
        template = CardTemplate.model_validate(template_create)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def update(self, template_id: int, template_update: CardTemplateUpdate) -> Optional[CardTemplate]:
        template = self.get_by_id(template_id)
        if not template:
            return None
        for key, value in template_update.model_dump(exclude_unset=True).items():
            setattr(template, key, value)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template_id: int) -> bool:
        template = self.get_by_id(template_id)
        if not template:
            return False
        self.db.delete(template)
        self.db.commit()
        return True
