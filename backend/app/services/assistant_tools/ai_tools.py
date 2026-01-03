"""
灵感助手工具函数集合（LangChain 原生工具实现）。
"""
import json
from typing import Dict, Any, List, Optional
from contextvars import ContextVar

from loguru import logger
from langchain_core.tools import tool

from app.services import nodes, agent_service, llm_config_service
from app.db.models import Card, CardType
import copy
from pydantic import BaseModel


class AssistantDeps:
    """灵感助手的依赖（用于传递 session 和 project_id）。"""

    def __init__(self, session, project_id: int):
        self.session = session
        self.project_id = project_id


# 使用 ContextVar 在每个请求上下文中注入依赖，避免为每个工具再包一层。
_assistant_deps_var: ContextVar[AssistantDeps | None] = ContextVar(
    "assistant_deps", default=None
)


def set_assistant_deps(deps: AssistantDeps) -> None:
    """为当前请求上下文设置助手依赖，在调用工具前必须先设置。"""

    _assistant_deps_var.set(deps)


def _get_deps() -> AssistantDeps:
    """获取当前请求上下文中的助手依赖。"""

    deps = _assistant_deps_var.get()
    if deps is None:
        raise RuntimeError(
            "AssistantDeps 未设置，请在调用助手工具前先调用 set_assistant_deps(...)。"
        )
    return deps


@tool
def search_cards(
    card_type: Optional[str] = None,
    title_keyword: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    搜索项目中的卡片列表。
    如果你需要查找特定类型的卡片（如“角色卡”），请务必指定 card_type。
    如果你需要查找特定标题的卡片，请指定 title_keyword。
    
    Args:
        card_type: 卡片类型名称（如：角色卡、场景卡、章节正文等）。建议先调用 list_card_types 获取可用类型。
        title_keyword: 标题中的关键词。
        limit: 返回结果数量上限，默认 20。
    
    Returns:
        success: True 表示成功，False 表示失败
        cards: 包含 id, title, type 的卡片对象列表
        count: 实际返回的卡片数量
    """

    deps = _get_deps()

    logger.info(f" [Assistant.search_cards] card_type={card_type}, keyword={title_keyword}")

    query = deps.session.query(Card).filter(Card.project_id == deps.project_id)
    
    if card_type:
        query = query.join(CardType).filter(CardType.name == card_type)
    
    if title_keyword:
        query = query.filter(Card.title.ilike(f'%{title_keyword}%'))
    
    cards = query.limit(limit).all()
    
    result = {
        "success": True,
        "cards": [
            {
                "id": c.id,
                "title": c.title,
                "type": c.card_type.name if c.card_type else "Unknown"
            }
            for c in cards
        ],
        "count": len(cards)
    }
    
    logger.info(f"✅ [Assistant.search_cards] 找到 {len(cards)} 个卡片")
    return result


@tool
def list_card_types() -> Dict[str, Any]:
    """
    获取本项目中所有可用的卡片类型列表。
    在调用 search_cards 或 create_card 之前，建议先调用此工具以了解可用的类型名称。
    
    Returns:
        success: True 表示成功
        card_types: 包含 id, name, description 的类型列表
    """
    deps = _get_deps()
    types = deps.session.query(CardType).all()
    return {
        "success": True,
        "card_types": [
            {"id": t.id, "name": t.name, "description": t.description}
            for t in types
        ]
    }


@tool
def create_card(
    card_type: str,
    title: str,
    content: Dict[str, Any],
    parent_card_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    创建新卡片
    
    Examples:
        # 在项目根目录创建角色卡
        create_card(card_type="角色卡", title="张三", content={...})
        
        # 在某个分卷大纲（card_id=42）下创建章节大纲
        create_card(card_type="章节大纲", title="第一章", content={...}, parent_card_id=42)
    
    Args:
        card_type: 卡片类型名称（如：角色卡、章节大纲、世界观设定等）
        title: 卡片标题
        content: 卡片内容（字典，需符合该类型的 Schema）
        parent_card_id: 父卡片ID（可选）
            * 如果提供，则在指定卡片下创建子卡片
            * 如果不提供，则在项目根目录创建
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息（失败时）
        card_id: 卡片ID
        card_title: 卡片标题
        card_type: 卡片类型
        parent_id: 父卡片ID（None表示在根目录创建）
        parent_title: 父卡片标题（如果有父卡片）
        parent_type: 父卡片类型（如果有父卡片）
        message: 用户友好的消息
    """

    deps = _get_deps()

    logger.info(
        f" [Assistant.create_card] type={card_type}, title={title}, parent_id={parent_card_id}"
    )

    state = {
        "scope": {"project_id": deps.project_id},
        "touched_card_ids": set(),
    }

    # 构建 params，如果指定了父卡片ID，则添加到 parent 参数
    params = {
        "cardType": card_type,
        "title": title,
        "contentMerge": content
    }
    
    if parent_card_id is not None:
        params["parent"] = parent_card_id
        logger.info(f"  指定父卡片ID: {parent_card_id}")
    else:
        params["parent"] = "$projectRoot"
        logger.info(f"  在项目根目录创建")
    
    result = nodes.node_card_upsert_child_by_title(
        session=deps.session,
        state=state,
        params=params,
    )

    # 提交事务（重要！）
    deps.session.commit()

    logger.info(f"✅ [Assistant.create_card] 创建成功: {result}")
    
    # 获取创建的卡片以返回完整信息
    created_card = result.get("card")
    response = {
        "success": True,
        "card_id": created_card.id if created_card else result.get("card_id"),
        "card_title": created_card.title if created_card else result.get("card_title", title),
        "card_type": card_type,
        "parent_id": created_card.parent_id if created_card else parent_card_id,
        "message": f"✅ 已创建{card_type}「{title}」"
    }
    
    # 如果有父卡片，添加父卡片信息
    if created_card and created_card.parent_id and created_card.parent:
        response["parent_title"] = created_card.parent.title
        response["parent_type"] = (
            created_card.parent.card_type.name
            if created_card.parent.card_type
            else "Unknown"
        )
    
    return response

@tool
def modify_card_field(
    card_id: int,
    field_path: str,
    new_value: Any,
) -> Dict[str, Any]:
    """
    修改指定卡片的字段内容
    
    使用场景：当用户要求将内容写入某卡片时，必须调用此工具执行
    
    Examples:
        - modify_card_field(card_id=27, field_path="overview", new_value="这是新的概述内容...")
        - modify_card_field(card_id=15, field_path="content.name", new_value="林风")
        - modify_card_field(card_id=8, field_path="chapter_outline_list", new_value=[...])
    
    Args:
        card_id: 目标卡片的ID（从项目结构树中查找）
        field_path: 字段路径，支持两种格式：
            * 简单字段："overview"、"stage_name" 等
            * 嵌套字段："content.overview"、"content.chapter_outline_list" 等
        new_value: 要设置的新值（可以是字符串、数字、列表、字典等）
    
    
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息
        card_id: 卡片ID
        card_title: 卡片标题
        field_path: 字段路径
        new_value: 新的值
        message: 用户友好的消息
    """

    deps = _get_deps()

    logger.info(f" [Assistant.modify_card_field] card_id={card_id}, path={field_path}")
    logger.info(f"  新值类型: {type(new_value)}")

    try:
        # 验证卡片存在性
        card = deps.session.get(Card, card_id)
        if not card or card.project_id != deps.project_id:
            logger.warning(f"⚠️ 卡片 {card_id} 不存在或不属于当前项目")
            return {
                "success": False,
                "error": f"卡片 {card_id} 不存在或不属于当前项目",
            }

        logger.info(f"  卡片标题: {card.title}")
        logger.info(f"  修改前: {card.content}")
        
        # 构造工作流节点所需的 state
        state = {"card": card, "touched_card_ids": set()}

        # 调用工作流节点函数
        nodes.node_card_modify_content(
            session=deps.session,
            state=state,
            params={"setPath": field_path, "setValue": new_value},
        )

        # 提交事务（重要！）
        deps.session.commit()

        # 刷新卡片数据
        deps.session.refresh(card)
        
        logger.info(f"  修改后: {card.content}")
        logger.info(f"✅ [Assistant.modify_card_field] 修改成功")
        
        return {
            "success": True,
            "card_id": card_id,
            "card_title": card.title,
            "field_path": field_path,
            "new_value": new_value,
            "message": f"✅ 已更新「{card.title}」的 {field_path.replace('content.', '')}"
        }
    
    except Exception as e:
        logger.error(f"❌ [Assistant.modify_card_field] 修改失败: {e}")
        return {"success": False, "error": f"修改失败: {str(e)}"}

@tool
def batch_create_cards(
    card_type: str,
    cards: List[Dict[str, Any]],
    parent_card_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    批量创建同类型卡片
    
    Args:
        card_type: 卡片类型名称
        cards: 卡片数据列表，每项包含 title 和 content
        parent_card_id: 父卡片ID（可选）
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息
        total: 卡片总数
        success_count: 成功创建的卡片数量
        failed_count: 失败创建的卡片数量
        results: 创建结果列表
    """

    deps = _get_deps()

    logger.info(
        f" [Assistant.batch_create_cards] type={card_type}, count={len(cards)}"
    )

    results = []
    
    for card_data in cards:
        try:
            title = card_data.get("title", "")
            content = card_data.get("content", {})

            # 复用单卡片创建逻辑
            result = create_card(  # type: ignore[call-arg]
                card_type=card_type,
                title=title,
                content=content,
                parent_card_id=parent_card_id,
            )
            results.append({
                "title": title,
                "status": "success",
                "card_id": result["card_id"]
            })
        except Exception as e:
            logger.error(f"批量创建失败: {card_data.get('title', 'unknown')} - {e}")
            results.append({
                "title": card_data.get("title", "unknown"),
                "status": "failed",
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r["status"] == "success")

    logger.info(
        f"✅ [Assistant.batch_create_cards] 成功 {success_count}/{len(cards)}"
    )

    return {
        "success": True,
        "total": len(cards),
        "success_count": success_count,
        "failed_count": len(cards) - success_count,
        "results": results
    }

@tool
def get_card_type_schema(
    card_type_name: str,
) -> Dict[str, Any]:
    """
    获取指定卡片类型的 JSON Schema 定义
    
    使用场景：当需要创建卡片但不清楚其结构时调用
    
    Args:
        card_type_name: 卡片类型名称
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息
        card_type: 卡片类型名称
        schema: 卡片类型的 JSON Schema 定义
        description: 卡片类型的描述
    """

    deps = _get_deps()

    logger.info(f" [Assistant.get_card_type_schema] card_type={card_type_name}")

    card_type = (
        deps.session.query(CardType)
        .filter(CardType.name == card_type_name)
        .first()
    )
    
    if not card_type:
        logger.warning(
            f"⚠️ [Assistant.get_card_type_schema] 卡片类型 '{card_type_name}' 不存在"
        )
        return {
            "success": False,
            "error": f"卡片类型 '{card_type_name}' 不存在"
        }
    
    result = {
        "success": True,
        "card_type": card_type_name,
        "schema": card_type.json_schema or {},
        "description": f"卡片类型 '{card_type_name}' 的完整结构定义"
    }
    
    logger.info(f"✅ [Assistant.get_card_type_schema] 已返回 Schema：{result}")
    return result


@tool
def get_card_content(
    card_id: int,
) -> Dict[str, Any]:
    """
    获取指定卡片的详细内容
    
    使用场景：需要查看卡片的完整数据时调用
    
    Args:
        card_id: 卡片ID
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息（失败时）
        card_id: 卡片ID
        title: 卡片标题
        card_type: 卡片类型
        parent_id: 父卡片ID（None表示根级卡片）
        parent_title: 父卡片标题（如果有父卡片）
        parent_type: 父卡片类型（如果有父卡片）
        content: 卡片内容
        created_at: 卡片创建时间
    """

    deps = _get_deps()

    logger.info(f" [Assistant.get_card_content] card_id={card_id}")

    card = deps.session.query(Card).filter(Card.id == card_id).first()
    
    if not card:
        logger.warning(f"⚠️ [Assistant.get_card_content] 卡片 #{card_id} 不存在")
        return {
            "success": False,
            "error": f"卡片 #{card_id} 不存在"
        }
    
    result = {
        "success": True,
        "card_id": card.id,
        "title": card.title,
        "card_type": card.card_type.name if card.card_type else "Unknown",
        "parent_id": card.parent_id,  # 父卡片ID，用于了解层级关系
        "content": card.content or {},
        "created_at": str(card.created_at) if card.created_at else None
    }
    
    # 如果有父卡片，添加父卡片信息
    if card.parent_id and card.parent:
        result["parent_title"] = card.parent.title
        result["parent_type"] = card.parent.card_type.name if card.parent.card_type else "Unknown"
    
    logger.info(
        f"✅ [Assistant.get_card_content] 已返回卡片内容 (parent_id={card.parent_id})"
    )
    return result


@tool
def replace_field_text(
    card_id: int,
    field_path: str,
    old_text: str,
    new_text: str,
) -> Dict[str, Any]:
    """
    替换卡片字段中的指定文本片段
    
    使用场景：当用户对长文本字段的某部分内容不满意，希望只替换该部分时调用
    适用于章节正文、大纲描述等长文本字段的局部修改
    
    Examples:
        1. 精确匹配（短文本）：
        replace_field_text(card_id=42, field_path="content", 
                            old_text="林风犹豫了片刻", 
                            new_text="林风毫不犹豫地")
        
        2. 模糊匹配（长文本）：
        replace_field_text(card_id=42, field_path="content",
                            old_text="少年面色苍白，额头青筋暴起...现在却成了个废人。",
                            new_text="新的完整段落内容...")
    
    Args:
        card_id: 目标卡片的ID
        field_path: 字段路径（如 "content" 表示章节正文，"overview" 表示概述）
        old_text: 要被替换的原文片段，支持两种模式：
            1. 精确匹配：提供完整的原文（适用于短文本，50字以内）
            2. 模糊匹配：提供开头10字 + "..." + 结尾10字（适用于长文本，50字以上）
        new_text: 新的文本内容
    
    
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息
        card_title: 卡片标题
        replaced_count: 替换的次数
        message: 用户友好的消息
    """

    deps = _get_deps()

    logger.info(f" [Assistant.replace_field_text] card_id={card_id}, path={field_path}")
    logger.info(f"  要替换的文本长度: {len(old_text)} 字符")
    logger.info(f"  新文本长度: {len(new_text)} 字符")

    try:
        # 验证卡片存在性和归属
        card = deps.session.get(Card, card_id)
        if not card or card.project_id != deps.project_id:
            logger.warning(f"⚠️ 卡片 {card_id} 不存在或不属于当前项目")
            return {
                "success": False,
                "error": f"卡片 {card_id} 不存在或不属于当前项目",
            }

        logger.info(f"  卡片标题: {card.title}")
        
        # 构造工作流节点所需的 state
        state = {"touched_card_ids": set()}

        # 调用工作流节点函数
        result = nodes.node_card_replace_field_text(
            session=deps.session,
            state=state,
            params={
                "card_id": card_id,
                "field_path": field_path,
                "old_text": old_text,
                "new_text": new_text,
            },
        )

        # 如果节点执行失败，直接返回错误
        if not result.get("success"):
            logger.warning(
                f"⚠️ [Assistant.replace_field_text] 节点执行失败: {result.get('error')}"
            )
            return result
        
        # 提交事务（重要！）
        deps.session.commit()

        logger.info(f"✅ [Assistant.replace_field_text] 替换成功")

        # 添加用户友好的消息
        result["message"] = (
            f"✅ 已在「{result.get('card_title')}」的 {field_path.replace('content.', '')} 中替换 "
            f"{result.get('replaced_count')} 处内容"
        )

        return result

    except Exception as e:
        logger.error(f"❌ [Assistant.replace_field_text] 替换失败: {e}")
        return {"success": False, "error": f"替换失败: {str(e)}"}


@tool
def delete_card(card_id: int) -> dict:
    """
    删除指定的卡片。
    注意：此操作不可逆，请谨慎使用。
    """
    deps = _get_deps()
    logger.info(f" [Assistant.delete_card] card_id={card_id}")

    try:
        # 验证卡片存在性和归属
        card = deps.session.get(Card, card_id)
        if not card or card.project_id != deps.project_id:
            logger.warning(f"⚠️ 卡片 {card_id} 不存在或不属于当前项目")
            return {
                "success": False,
                "error": f"卡片 {card_id} 不存在或不属于当前项目",
            }

        title = card.title
        
        # 构造工作流节点所需的 state
        state = {"scope": {"card_id": card_id}}

        # 调用工作流节点函数
        result = nodes.node_card_delete(
            session=deps.session,
            state=state,
            params={"target": "$self"},
        )

        # 如果节点执行失败，直接返回错误
        if not result.get("success"):
            logger.warning(
                f"⚠️ [Assistant.delete_card] 节点执行失败: {result.get('error')}"
            )
            return result
        
        # 提交事务
        deps.session.commit()

        logger.info(f"✅ [Assistant.delete_card] 删除成功")

        return {
            "success": True,
            "message": f"✅ 已成功删除卡片「{title}」(ID: {card_id})",
            "card_id": card_id
        }

    except Exception as e:
        logger.error(f"❌ [Assistant.delete_card] 删除失败: {e}")
        return {"success": False, "error": f"删除失败: {str(e)}"}


@tool
async def create_card_from_inspiration(
    card_type: str,
    title: str,
    inspiration_text: str,
    parent_card_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    根据灵感描述自动生成并创建新卡片。
    
    使用场景：当用户有一个模糊的想法（如“帮我设计一个反派角色，性格阴影”），
    助手应调用此工具，它会自动根据灵感生成符合 Schema 的内容并创建卡片。
    
    Args:
        card_type: 卡片类型名称（如：角色卡、世界观设定等）
        title: 卡片标题
        inspiration_text: 灵感描述文本
        parent_card_id: 父卡片ID（可选）
    
    Returns:
        success: True 表示成功，False 表示失败
        error: 错误信息
        card_id: 新创建的卡片ID
        message: 用户友好的消息
    """

    deps = _get_deps()
    logger.info(f" [Assistant.create_card_from_inspiration] type={card_type}, title={title}")

    try:
        # 1. 获取 Schema
        schema_resp = get_card_type_schema(card_type_name=card_type)
        if not schema_resp.get("success"):
            return schema_resp
        
        schema = schema_resp.get("schema")
        
        # 2. 调用 AI 生成内容
        configs = llm_config_service.get_llm_configs(deps.session)
        llm_config_id = configs[0].id if configs else 1
        
        system_prompt = f"你是一个专业的小说创作助手。请根据灵感描述，为一个类型为「{card_type}」的卡片生成详细内容。请严格按照提供的 JSON Schema 生成内容，仅返回 JSON 对象。"
        user_prompt = f"卡片标题：{title}\n灵感描述：{inspiration_text}\n\n请生成符合以下 Schema 的内容：\n{json.dumps(schema, ensure_ascii=False)}"

        logger.info(f"  正在调用 AI 生成内容...")
        
        # 动态创建一个 Pydantic 模型用于解析
        class DynamicContent(BaseModel):
            content: Dict[str, Any]

        # 实际上我们只需要生成符合 schema 的字典
        # 这里简化处理，直接让 AI 返回符合 schema 的 JSON
        result = await agent_service.run_llm_agent(
            session=deps.session,
            llm_config_id=llm_config_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=dict # 期望返回字典
        )
        
        generated_content = result if isinstance(result, dict) else {}
        
        # 3. 创建卡片
        create_res = create_card( # type: ignore[call-arg]
            card_type=card_type,
            title=title,
            content=generated_content,
            parent_card_id=parent_card_id
        )
        
        if create_res.get("success"):
            create_res["message"] = f"✨ 已根据灵感自动生成并创建{card_type}「{title}」"
        
        return create_res

    except Exception as e:
        logger.error(f"❌ [Assistant.create_card_from_inspiration] 失败: {e}")
        return {"success": False, "error": f"生成并创建失败: {str(e)}"}


# 导出所有 LangChain 工具（已通过 @tool 装饰）
ASSISTANT_TOOLS = [
    search_cards,
    create_card,
    modify_card_field,
    replace_field_text,
    batch_create_cards,
    get_card_type_schema,
    get_card_content,
    delete_card,
    create_card_from_inspiration,
]

ASSISTANT_TOOL_REGISTRY = {tool.name: tool for tool in ASSISTANT_TOOLS}

ASSISTANT_TOOL_DESCRIPTIONS = {
    tool.name: {
        "description": tool.description,
        "args": tool.args,
    }
    for tool in ASSISTANT_TOOLS
}
