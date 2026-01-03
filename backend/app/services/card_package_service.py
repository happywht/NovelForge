from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.db.models import Card, CardType
from loguru import logger
import json
from datetime import datetime

class CardPackageService:
    def __init__(self, session: Session):
        self.session = session

    def export_package(self, root_card_id: int) -> Dict[str, Any]:
        """
        Export a card and its descendants as a package.
        """
        root_card = self.session.get(Card, root_card_id)
        if not root_card:
            raise ValueError(f"Card {root_card_id} not found")

        # Recursive function to gather cards
        cards_to_export = []
        
        def _recurse(card: Card):
            # Serialize card
            card_data = card.model_dump(exclude={'id', 'project_id', 'parent_id', 'created_at', 'project', 'parent', 'children', 'card_type'})
            # Add type name for resolution on import
            card_data['card_type_name'] = card.card_type.name if card.card_type else None
            # Keep original ID for relative parent mapping within the package
            card_data['original_id'] = card.id
            card_data['original_parent_id'] = card.parent_id
            
            cards_to_export.append(card_data)
            
            # Fetch children
            children = self.session.exec(select(Card).where(Card.parent_id == card.id)).all()
            for child in children:
                _recurse(child)

        _recurse(root_card)

        return {
            "version": 1,
            "exported_at": datetime.utcnow().isoformat(),
            "root_card_title": root_card.title,
            "cards": cards_to_export
        }

    def import_package(self, project_id: int, target_parent_id: Optional[int], package_data: Dict[str, Any]) -> int:
        """
        Import a package into a project. Returns the ID of the new root card.
        """
        cards_data = package_data.get("cards", [])
        if not cards_data:
            raise ValueError("Package contains no cards")

        # Map original_id -> new_card_instance
        id_map: Dict[int, Card] = {}
        
        # Pre-fetch card types to avoid repeated queries
        card_types = {ct.name: ct for ct in self.session.exec(select(CardType)).all()}

        # First pass: Create all cards (without setting parent_id yet, or setting to None)
        # We need to process them in an order that ensures parents exist, OR we can just create them all and then link.
        # Since we have a flat list, let's create instances first.
        
        new_cards = []
        
        # Find the root of the package (the one whose parent is NOT in the package)
        package_ids = set(c['original_id'] for c in cards_data)
        package_root = None
        
        for c_data in cards_data:
            original_id = c_data['original_id']
            original_parent_id = c_data.get('original_parent_id')
            
            # Determine if this is the root of the import
            is_root = original_parent_id not in package_ids
            if is_root:
                package_root = c_data
            
            # Resolve card type
            type_name = c_data.get('card_type_name')
            card_type = card_types.get(type_name)
            if not card_type:
                # Fallback to a default type or error? Let's fallback to 'Folder' or similar if exists, else skip or error.
                # For now, let's assume 'Text' or 'Folder' exists, or just use the first available type.
                # Better: Log warning and use a safe default like '通用' if available, or just fail.
                logger.warning(f"Card type '{type_name}' not found, falling back to default.")
                card_type = list(card_types.values())[0] # Risky but keeps it moving

            # Create new card instance
            new_card = Card(
                title=c_data['title'],
                project_id=project_id,
                card_type_id=card_type.id,
                content=c_data.get('content', {}),
                display_order=c_data.get('display_order', 0),
                ai_params=c_data.get('ai_params'),
                json_schema=c_data.get('json_schema'),
                ai_context_template=c_data.get('ai_context_template')
            )
            self.session.add(new_card)
            self.session.flush() # Get ID
            
            id_map[original_id] = new_card
            new_cards.append((new_card, c_data))

        # Second pass: Link parents
        for new_card, c_data in new_cards:
            original_parent_id = c_data.get('original_parent_id')
            
            if original_parent_id in id_map:
                # Parent is inside the package
                new_card.parent_id = id_map[original_parent_id].id
            else:
                # Parent is outside (this is the root of the package)
                new_card.parent_id = target_parent_id
            
            self.session.add(new_card)

        self.session.commit()
        
        if package_root:
            return id_map[package_root['original_id']].id
        return 0
