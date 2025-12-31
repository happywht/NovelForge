from app.db.session import get_session
from app.db.models import CardType
import json

def dump_schemas():
    session = next(get_session())
    types = ['金手指', '世界观设定', '核心蓝图']
    results = {}
    for t in types:
        ct = session.query(CardType).filter(CardType.name == t).first()
        if ct:
            results[t] = ct.json_schema
        else:
            results[t] = "Not Found"
    
    with open("full_schemas.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Schemas dumped to full_schemas.json")

if __name__ == "__main__":
    dump_schemas()
