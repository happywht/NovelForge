import os
import sys
from sqlmodel import Session, select

# 添加项目根目录到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.db.session import get_session
from app.db.models import Card, CardType, Project
from app.services.assistant_tools.ai_tools import delete_card, create_card
from app.services.assistant_tools.ai_tools import AssistantDeps, set_assistant_deps

def test_card_deletion():
    session = next(get_session())
    project_id = 2  # 测试小说
    
    # 设置助手工具所需的依赖上下文
    deps = AssistantDeps(session=session, project_id=project_id)
    set_assistant_deps(deps)
    
    print(f"--- 开始测试卡片删除功能 ---")
    
    # 1. 创建一个测试卡片
    # 先获取一个卡片类型
    card_type = session.exec(select(CardType).where(CardType.name == "角色卡")).first()
    if not card_type:
        print("错误: 未找到 '角色卡' 类型")
        return

    print(f"正在创建测试卡片...")
    result_create = create_card.invoke({
        "card_type": "角色卡",
        "title": "测试删除角色",
        "content": {"name": "测试删除角色", "description": "这是一个用于测试删除功能的临时卡片"}
    })
    
    if not result_create.get("success"):
        print(f"创建卡片失败: {result_create.get('error')}")
        return
    
    card_id = result_create.get("card_id")
    print(f"成功创建卡片, ID: {card_id}")
    
    # 2. 验证卡片在数据库中存在
    card = session.get(Card, card_id)
    if card:
        print(f"验证成功: 卡片 {card_id} 已存在于数据库中")
    else:
        print(f"验证失败: 未在数据库中找到卡片 {card_id}")
        return
    
    # 3. 使用 delete_card 工具删除卡片
    print(f"正在调用 delete_card 工具删除卡片 {card_id}...")
    result_delete = delete_card.invoke({"card_id": card_id})
    
    if result_delete.get("success"):
        print(f"工具返回成功: {result_delete.get('message')}")
    else:
        print(f"工具返回失败: {result_delete.get('error')}")
        return
    
    # 4. 再次验证卡片是否已删除
    # 注意：由于 delete_card 内部已经 commit 了，我们需要刷新 session 或重新获取
    session.expire_all()
    card_after = session.get(Card, card_id)
    if not card_after:
        print(f"验证成功: 卡片 {card_id} 已从数据库中删除")
    else:
        print(f"验证失败: 卡片 {card_id} 仍然存在于数据库中")
        return

    print(f"--- 卡片删除功能测试通过 ---")

if __name__ == "__main__":
    test_card_deletion()
