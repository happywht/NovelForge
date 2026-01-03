import re
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.db.models import Card, CardType
from loguru import logger

class ReverseArchitectService:
    def __init__(self, session: Session):
        self.session = session

    def split_text(self, text: str, regex_pattern: str = r'(第[一二三四五六七八九十百千万零\d]+[章节回].*)') -> List[Dict[str, str]]:
        """
        Split a long text into chapters based on a regex pattern.
        """
        # Find all matches for chapter headers
        matches = list(re.finditer(regex_pattern, text))
        
        if not matches:
            # If no chapters found, return the whole text as a single chapter
            return [{"title": "全文导入", "content": text.strip()}]

        chapters = []
        for i in range(len(matches)):
            start_index = matches[i].start()
            end_index = matches[i+1].start() if i + 1 < len(matches) else len(text)
            
            title = matches[i].group(0).strip()
            # Content is everything between this header and the next (excluding the header itself)
            content = text[matches[i].end():end_index].strip()
            
            chapters.append({
                "title": title,
                "content": content
            })
            
        return chapters

    def batch_import_chapters(self, project_id: int, text: str, regex_pattern: Optional[str] = None) -> List[int]:
        """
        Split text and create cards for each chapter.
        """
        pattern = regex_pattern or r'(第[一二三四五六七八九十百千万零\d]+[章节回].*)'
        chapters = self.split_text(text, pattern)
        
        if not chapters:
            return []

        # 1. Find or create "故事大纲" folder
        # First, find the "故事大纲" card type
        stmt_type = select(CardType).where(CardType.name == "故事大纲")
        outline_type = self.session.exec(stmt_type).first()
        
        # Then, find or create a card of this type at root
        stmt_folder = select(Card).where(
            Card.project_id == project_id, 
            Card.card_type_id == outline_type.id if outline_type else -1,
            Card.parent_id == None
        )
        outline_folder = self.session.exec(stmt_folder).first()
        
        if not outline_folder:
            if not outline_type:
                # Fallback: find any type that looks like a folder or just use the first one
                outline_type = self.session.exec(select(CardType)).first()
            
            outline_folder = Card(
                title="故事大纲 (导入)",
                project_id=project_id,
                card_type_id=outline_type.id,
                parent_id=None,
                display_order=0,
                content={}
            )
            self.session.add(outline_folder)
            self.session.flush()

        # 2. Find "章节正文" card type
        stmt_chapter_type = select(CardType).where(CardType.name == "章节正文")
        chapter_type = self.session.exec(stmt_chapter_type).first()
        if not chapter_type:
            chapter_type = outline_type # Fallback

        # 3. Create cards for each chapter
        created_ids = []
        start_order = len(self.session.exec(select(Card).where(Card.parent_id == outline_folder.id)).all())
        
        for i, ch in enumerate(chapters):
            new_card = Card(
                title=ch["title"],
                project_id=project_id,
                card_type_id=chapter_type.id,
                parent_id=outline_folder.id,
                display_order=start_order + i,
                content={
                    "title": ch["title"],
                    "content": ch["content"],
                    "chapter_number": i + 1
                }
            )
            self.session.add(new_card)
            self.session.flush()
            created_ids.append(new_card.id)
            
        self.session.commit()
        return created_ids
