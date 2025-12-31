from app.db.session import get_session
from app.db.models import Card, CardType
from sqlalchemy import select
import json

def debug_card_content():
    session = next(get_session())
    types = ['金手指', '世界观设定', '核心蓝图']
    results = {}
    for t in types:
        # 使用 session.query 这种更传统的方式，通常直接返回对象
        card = session.query(Card).join(CardType).filter(CardType.name == t).first()
        
        if card:
            results[t] = {
                "id": card.id,
                "title": card.title,
                "content": card.content
            }
        else:
            results[t] = "Not Found"
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_card_content()
