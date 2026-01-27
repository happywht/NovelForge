from __future__ import annotations

from typing import Any, Optional, List, Dict, Callable
import re
import copy
import json
import asyncio
from sqlmodel import Session, select
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.db.models import Card, CardType
from loguru import logger
from app.services import agent_service, context_service, memory_service, llm_config_service, prompt_service


# ==================== 节点注册机制 ====================
# 使用装饰器自动注册工作流节点，避免手动维护映射表

_NODE_REGISTRY: Dict[str, Callable] = {}


def register_node(node_type: str):
    """
    装饰器：自动注册工作流节点
    
    用法:
        @register_node("Card.Read")
        def node_card_read(session, state, params):
            ...
    """
    def decorator(func: Callable):
        _NODE_REGISTRY[node_type] = func
        logger.debug(f"[节点注册] {node_type} -> {func.__name__}")
        return func
    return decorator


def get_registered_nodes() -> Dict[str, Callable]:
    """获取所有已注册的节点"""
    return _NODE_REGISTRY.copy()


def get_node_types() -> List[str]:
    """获取所有已注册的节点类型名称"""
    return list(_NODE_REGISTRY.keys())


# ======================================================


def _parse_schema_fields(schema: dict, path: str = "$.content", max_depth: int = 5) -> List[dict]:
    """
    解析JSON Schema字段结构，支持嵌套对象和引用
    返回字段列表，每个字段包含: name, type, path, children(可选)
    """
    if max_depth <= 0:
        return []
    
    fields = []
    try:
        # 获取$defs用于解析引用
        defs = schema.get("$defs", {})
        
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return fields
            
        for field_name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue
            
            # 解析引用
            resolved_schema = _resolve_schema_ref(field_schema, defs)
            
            field_type = resolved_schema.get("type", "unknown")
            field_title = resolved_schema.get("title", field_name)
            field_description = resolved_schema.get("description", "")
            field_path = f"{path}.{field_name}"
            
            field_info = {
                "name": field_name,
                "title": field_title,
                "type": field_type,
                "path": field_path,
                "description": field_description,
                "required": field_name in schema.get("required", []),
                "expanded": False
            }
            
            # 处理anyOf类型（可选类型）
            if "anyOf" in resolved_schema:
                non_null_schema = None
                for any_schema in resolved_schema["anyOf"]:
                    if isinstance(any_schema, dict) and any_schema.get("type") != "null":
                        non_null_schema = _resolve_schema_ref(any_schema, defs)
                        break
                if non_null_schema:
                    resolved_schema = non_null_schema
                    field_type = resolved_schema.get("type", "unknown")
                    field_info["type"] = field_type
            
            # 处理嵌套对象
            if field_type == "object" and "properties" in resolved_schema:
                children = _parse_schema_fields(resolved_schema, field_path, max_depth - 1)
                if children:
                    field_info["children"] = children
                    field_info["expandable"] = True
            
            # 处理数组类型
            elif field_type == "array" and "items" in resolved_schema:
                items_schema = resolved_schema["items"]
                items_resolved = _resolve_schema_ref(items_schema, defs)
                
                if items_resolved.get("type") == "object" and "properties" in items_resolved:
                    children = _parse_schema_fields(items_resolved, f"{field_path}[0]", max_depth - 1)
                    if children:
                        field_info["children"] = children
                        field_info["expandable"] = True
                        field_info["array_item_type"] = "object"
                else:
                    # 简单数组类型
                    field_info["array_item_type"] = items_resolved.get("type", "unknown")
            
            fields.append(field_info)
            
    except Exception as e:
        logger.warning(f"解析Schema字段失败: {e}")
    
    return fields


def _resolve_schema_ref(schema: dict, defs: dict) -> dict:
    """解析Schema引用"""
    if not isinstance(schema, dict):
        return schema
    
    # 处理$ref引用
    if "$ref" in schema:
        ref_path = schema["$ref"]
        if ref_path.startswith("#/$defs/"):
            ref_name = ref_path.replace("#/$defs/", "")
            if ref_name in defs:
                resolved = defs[ref_name]
                # 保留原schema的title和description
                if "title" in schema:
                    resolved = {**resolved, "title": schema["title"]}
                if "description" in schema:
                    resolved = {**resolved, "description": schema["description"]}
                return resolved
    
    return schema


def _get_card_by_id(session: Session, card_id: int) -> Optional[Card]:
    try:
        return session.get(Card, int(card_id))
    except Exception:
        return None


def _get_by_path(obj: Any, path: str) -> Any:
    print(f"DEBUG: _get_by_path path={path}")
    # 极简路径解析：支持 $.content.a.b.c 与 $.a.b
    if not path or not isinstance(path, str):
        return None
    if not path.startswith("$."):
        return None
    parts = path[2:].split(".")
    # 处理根 '$'：若 obj 为 {"$": base} 则先取出 base
    if isinstance(obj, dict) and "$" in obj:
        cur: Any = obj.get("$")
    else:
        cur = obj
    for p in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            try:
                cur = getattr(cur, p)
            except Exception:
                return None
    return cur


def _set_by_path(obj: Dict[str, Any], path: str, value: Any) -> bool:
    """按JSONPath设置值
    
    Args:
        obj: 目标对象
        path: JSONPath路径（必须以$.开头）
        value: 要设置的值
    
    Returns:
        bool: 是否设置成功
    """
    if not isinstance(obj, dict) or not isinstance(path, str) or not path.startswith("$."):
        return False
    
    parts = path[2:].split(".")
    cur: Dict[str, Any] = obj
    
    # 遍历到倒数第二层，确保路径存在
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]  # type: ignore[assignment]
    
    # 设置最后一层的值
    cur[parts[-1]] = value
    return True


_TPL_PATTERN = re.compile(r"\{([^{}]+)\}")


def _resolve_expr(expr: str, state: dict) -> Any:
    expr = expr.strip()
    # index（循环序号，从 1 开始）
    if expr == "index":
        return (state.get("item") or {}).get("index")
    # item.xxx
    if expr.startswith("item."):
        item = state.get("item") or {}
        return _get_by_path({"item": item}, "$." + expr)
    # current.xxx / current.card.xxx
    if expr.startswith("current."):
        cur = state.get("current") or {}
        return _get_by_path({"current": cur}, "$." + expr)
    # scope.xxx
    if expr.startswith("scope."):
        scope = state.get("scope") or {}
        return _get_by_path({"scope": scope}, "$." + expr)
    # $.content.xxx 针对当前 card
    if expr.startswith("$."):
        card = (state.get("current") or {}).get("card") or state.get("card")
        base = {"content": getattr(card, "content", {})} if card else {}
        return _get_by_path({"$": base}, expr)
    return None


def _to_name(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, dict):
        for key in ("name", "title", "label", "content"):
            v = x.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, dict):
                nn = v.get("name") or v.get("title")
                if isinstance(nn, str) and nn.strip():
                    return nn.strip()
    return str(x).strip()


def _to_name_list(seq: Any) -> List[str]:
    if not isinstance(seq, list):
        return []
    out: List[str] = []
    for it in seq:
        name = _to_name(it)
        if name:
            out.append(name)
    # 去重保持顺序
    seen = set()
    unique: List[str] = []
    for n in out:
        if n not in seen:
            unique.append(n)
            seen.add(n)
    return unique


def _render_value(val: Any, state: dict) -> Any:
    """
    模板渲染：
    - 字符串：{item.xxx} / {current.card.content.xxx} / {scope.xxx} / {index} / {$.content.xxx}
    - 对象：支持 {"$toNameList": "item.entity_list"} 快捷转换
    - 列表/对象：递归渲染
    """
    if isinstance(val, dict):
        if "$toNameList" in val and isinstance(val.get("$toNameList"), str):
            seq = _resolve_expr(val["$toNameList"], state)
            return _to_name_list(seq)
        return {k: _render_value(v, state) for k, v in val.items()}
    if isinstance(val, list):
        return [_render_value(v, state) for v in val]
    if isinstance(val, str):
        # 单一表达式直接返回原类型
        m = _TPL_PATTERN.fullmatch(val.strip())
        if m:
            resolved = _resolve_expr(m.group(1), state)
            return resolved
        # 内嵌模板，最终还是字符串
        def repl(match: re.Match) -> str:
            expr = match.group(1)
            res = _resolve_expr(expr, state)
            if isinstance(res, (dict, list)):
                return str(res)
            return "" if res is None else str(res)
        return _TPL_PATTERN.sub(repl, val)
    return val


def _get_from_state(path_expr: Any, state: dict) -> Any:
    # 兼容 path 字符串（$. / $item(. ) / $current(. ) / $scope(. ) / item. / scope. / current.）或直接值
    if isinstance(path_expr, str):
        p = path_expr.strip()
        if p in ("item", "$item"):
            return state.get("item")
        if p in ("current", "$current"):
            return state.get("current")
        if p in ("scope", "$scope"):
            return state.get("scope")
        # 统一映射到 _resolve_expr 可识别形式
        if p.startswith("$item."):
            return _resolve_expr("item." + p[len("$item."):], state)
        if p.startswith("$current."):
            return _resolve_expr("current." + p[len("$current."):], state)
        if p.startswith("$scope."):
            return _resolve_expr("scope." + p[len("$scope."):], state)
        if p.startswith(("item.", "current.", "scope.", "$.")):
            return _resolve_expr(p, state)
    return path_expr


@register_node("Card.Read")
def node_card_read(session: Session, state: dict, params: dict) -> dict:
    """
    Card.Read: 读取锚点卡片或指定 card_id，写入 state['card'] 并返回 {'card': Card}
    params:
      - target: "$self" | int(card_id)
      - type_name: 卡片类型名称，用于类型绑定和字段解析
    """
    target = params.get("target", "$self")
    type_name = params.get("type_name", "")
    
    card: Optional[Card] = None
    if target == "$self":
        scope = state.get("scope") or {}
        card_id = scope.get("card_id")
        if card_id:
            card = _get_card_by_id(session, card_id)
    else:
        try:
            card = _get_card_by_id(session, int(target))
        except Exception:
            card = None
    
    if not card:
        raise ValueError("Card.Read 未找到目标卡片")
    
    # 如果指定了类型名称，获取类型信息和字段结构
    card_type_info = None
    field_structure = None
    if type_name:
        from app.db.models import CardType
        card_type = session.exec(select(CardType).where(CardType.name == type_name)).first()
        if card_type and card_type.json_schema:
            card_type_info = {
                "id": card_type.id,
                "name": card_type.name,
                "schema": card_type.json_schema
            }
            # 解析字段结构
            field_structure = _parse_schema_fields(card_type.json_schema)
    
    state["card"] = card
    state["current"] = {
        "card": card,
        "card_type_info": card_type_info,
        "field_structure": field_structure
    }
    
    logger.info(f"[节点] 读取卡片 card_id={card.id} title={card.title} type={type_name}")
    return {
        "card": card,
        "card_type_info": card_type_info,
        "field_structure": field_structure
    }


@register_node("Card.ModifyContent")
def node_card_modify_content(session: Session, state: dict, params: dict) -> dict:
    """
    Card.ModifyContent: 将 params['contentMerge'](dict) 浅合并到当前 card.content
    兼容：setPath + setValue（直接设置路径值）
    params:
      - contentMerge: dict
      - setPath: string（可选，$.content.xxx 路径）
      - setValue: any（可选，支持表达式字符串）
    """
    card: Card = state.get("card")
    if not isinstance(card, Card):
        raise ValueError("Card.ModifyContent 缺少当前卡片，请先执行 Card.Read")

    # 优先处理 setPath/setValue
    set_path = params.get("setPath")
    if isinstance(set_path, str) and set_path:
        # 兼容 $card. 前缀（等价 $.）
        norm_path = set_path.strip()
        if norm_path.startswith("$card."):
            norm_path = "$." + norm_path[len("$card."):]
        
        # 如果路径不以 $. 开头，自动添加 $.content. 前缀
        if not norm_path.startswith("$."):
            norm_path = "$.content." + norm_path
        
        value_expr = params.get("setValue")
        value = _get_from_state(value_expr, state)
        
        # 使用深拷贝避免修改原始对象
        base = copy.deepcopy(dict(card.content or {}))
        
        # 规范化路径：如果以 $.content. 开头，去掉该前缀
        if norm_path.startswith("$.content."):
            content_path = "$." + norm_path[len("$.content."):]
        else:
            content_path = norm_path
        
        # 设置值
        _set_by_path(base, content_path, value)
        
        # 保存
        card.content = base
        session.add(card)
        session.commit()
        session.refresh(card)
        logger.info(f"[节点] 按路径设置内容 card_id={card.id} path={set_path} value={value}")
        # 标记受影响卡片
        try:
            touched: set = state.setdefault("touched_card_ids", set())  # type: ignore[assignment]
            touched.add(int(card.id))
        except Exception:
            pass
        state["card"] = card
        state["current"] = {"card": card}
        return {"card": card}

    # 默认走合并
    content_merge = params.get("contentMerge") or {}
    content_merge = _render_value(content_merge, state)
    if not isinstance(content_merge, dict):
        raise ValueError("contentMerge 需为对象")
    
    # 使用深拷贝避免修改原始对象
    base = copy.deepcopy(dict(card.content or {}))
    base.update(content_merge)
    card.content = base
    session.add(card)
    session.commit()
    session.refresh(card)
    # 标记受影响卡片
    try:
        touched2: set = state.setdefault("touched_card_ids", set())  # type: ignore[assignment]
        touched2.add(int(card.id))
    except Exception:
        pass
    state["card"] = card
    state["current"] = {"card": card}
    logger.info(f"[节点] 修改卡片内容完成 card_id={card.id} 合并键={list(content_merge.keys())}")
    return {"card": card}


@register_node("Card.UpsertChildByTitle")
def node_card_upsert_child_by_title(session: Session, state: dict, params: dict) -> dict:
    """
    Card.UpsertChildByTitle: 在目标父卡片下按标题创建/更新子卡。
    params:
      - cardType: str (卡片类型名称)
      - title: str (可使用模板: {item.title} / {index} / { $.content.volume_number } 等)
      - titlePath: string（兼容：从路径/表达式获取标题）
      - parent: "$self" | "$projectRoot" | 具体 card_id（可选，默认 $self）
      - useItemAsContent: bool (true 则以 state['item'] 作为 content)
      - contentMerge: dict （与 useItemAsContent 二选一，合并到 content）
      - contentTemplate: dict|list|str （直接模板渲染为 content，优先于 contentMerge）
      - contentPath: string（兼容：从路径/表达式获取内容）
    依赖：state['card'] 为默认父卡；可选 state['item'] 供模板取值。
    """
    parent: Optional[Card] = state.get("card")
    # 允许未先读父卡；若未提供 parent，则在项目根创建

    card_type_name = params.get("cardType")
    if not card_type_name:
        raise ValueError("参数 cardType 必填")
    ct: Optional[CardType] = session.exec(select(CardType).where(CardType.name == card_type_name)).first()
    if not ct:
        raise ValueError(f"未找到卡片类型: {card_type_name}")

    try:
        adapter = TypeAdapter(Any, config={'json_schema': ct.json_schema})
        validated_data = adapter.validate_python(params.get("content"))

    except ValidationError as e:
        raise ValueError(f"卡片类型 {card_type_name} 的结构校验失败: {e.errors()}，请确保按照json schema格式生成内容")

    raw_title: Optional[str] = params.get("title")
    if not raw_title:
        title_path = params.get("titlePath")
        if isinstance(title_path, str) and title_path:
            resolved_title = _get_from_state(title_path, state)
            if isinstance(resolved_title, (str, int, float)):
                raw_title = str(resolved_title)
    title = _render_value(raw_title, state) if isinstance(raw_title, str) else raw_title
    if not isinstance(title, str) or not title.strip():
        title = ct.name or "未命名"

    # 解析 parent 目标
    parent_spec = params.get("parent") or ("$self" if isinstance(parent, Card) else "$projectRoot")
    target_parent_id: Optional[int]
    project_id: int
    if parent_spec in ("$self", None):
        if not isinstance(parent, Card):
            raise ValueError("需要先读取父卡片或提供 parent 目标")
        target_parent_id = parent.id
        project_id = parent.project_id
    elif parent_spec in ("$root", "$projectRoot", "$project_root"):
        if isinstance(parent, Card):
            project_id = parent.project_id
        else:
            scope = state.get("scope") or {}
            project_id = int(scope.get("project_id"))
        target_parent_id = None
    else:
        p = _get_card_by_id(session, int(parent_spec))
        if not p:
            raise ValueError(f"未找到 parent 卡片: {parent_spec}")
        target_parent_id = p.id
        project_id = p.project_id

    # 查找同父、同类型、同标题是否已存在（避免不同类型同名卡片被误判为同一张）
    existing = session.exec(
        select(Card).where(
            Card.project_id == project_id,
            Card.parent_id == target_parent_id,
            Card.card_type_id == ct.id,
        )
    ).all()
    target = next((c for c in existing if str(c.title) == str(title)), None)

    use_item = bool(params.get("useItemAsContent"))
    # 若同时提供 useItemAsContent 与 contentMerge，则以 item 为基础再浅合并覆盖字段
    content_merge = params.get("contentMerge") if isinstance(params.get("contentMerge"), dict) else None
    content_template = params.get("contentTemplate") if isinstance(params.get("contentTemplate"), (dict, list, str)) else None
    content_path = params.get("contentPath") if isinstance(params.get("contentPath"), str) else None
    item = state.get("item") or {}

    if use_item:
        # 以当前 item 为基础，必要时再合并 contentMerge 进行字段覆盖
        content: Any = dict(item)
        if content_merge is not None:
            cm = _render_value(content_merge or {}, state)
            if isinstance(cm, dict):
                content.update(cm)
    else:
        if content_template is not None:
            content = _render_value(content_template, state)
            if not isinstance(content, dict):
                content = {"value": content}
        elif content_path:
            resolved = _get_from_state(content_path, state)
            content = resolved if isinstance(resolved, dict) else {"value": resolved}
        else:
            base = dict(target.content) if target else {}
            cm = _render_value(content_merge or {}, state)
            content = {**base, **(cm or {})}

    if target:
        target.content = content
        session.add(target)
        session.commit()
        session.refresh(target)
        result = target
        logger.info(f"[节点] 更新子卡完成 parent_id={target_parent_id} title={title} card_id={target.id}")
    else:
        new_card = Card(
            title=title,
            model_name=ct.model_name or ct.name,
            content=content,
            parent_id=target_parent_id,
            card_type_id=ct.id,
            json_schema=None,
            ai_params=None,
            project_id=project_id,
            display_order=len(existing),
            ai_context_template=ct.default_ai_context_template,
        )
        session.add(new_card)
        session.commit()
        session.refresh(new_card)
        result = new_card
        logger.info(f"[节点] 创建子卡完成 parent_id={target_parent_id} title={title} card_id={new_card.id}")

    state["last_child"] = result
    state["current"] = {"card": result}
    # 标记受影响卡片
    try:
        touched3: set = state.setdefault("touched_card_ids", set())  # type: ignore[assignment]
        touched3.add(int(getattr(result, "id", 0)))
        if isinstance(parent, Card) and parent.id:
            touched3.add(int(parent.id))
    except Exception:
        pass
    return {"card": result}


@register_node("List.ForEach")
async def node_list_foreach(session: Session, state: dict, params: dict, body_executor):
    """
    List.ForEach: 遍历列表并为每个元素执行 body 节点。
    params:
      - listPath: string 例如 "$.content.character_cards"
      - list: 任意（兼容：字符串路径 or 直接数组）
    """
    list_path = params.get("listPath")
    seq: Any = None
    if not isinstance(list_path, str) or not list_path:
        raw = params.get("list")
        logger.info(f"[节点] List.ForEach 原始 list 参数 type={type(raw).__name__} value={raw!r}")
        if isinstance(raw, list):
            seq = raw
        elif isinstance(raw, dict):
            # 支持 { path: '$.content.xxx' }
            cand = raw.get("path") or raw.get("listPath")
            if isinstance(cand, str) and cand:
                seq = _get_from_state(cand, state)
        elif isinstance(raw, str) and raw:
            seq = _get_from_state(raw.strip(), state)
    if seq is None:
        if not isinstance(list_path, str) or not list_path:
            logger.warning("[节点] List.ForEach 缺少 listPath")
            return
        card = state.get("card") or (state.get("current") or {}).get("card")
        base = {"content": getattr(card, "content", {})} if card else {}
        seq = _get_by_path({"$": base}, list_path) or []
    if not isinstance(seq, list):
        logger.warning(f"[节点] List.ForEach 取值非列表 path={list_path}")
        return
    logger.info(f"[节点] List.ForEach 解析完成，长度={len(seq)}")
    for idx, it in enumerate(seq, start=1):
        state["item"] = {"index": idx, **(it if isinstance(it, dict) else {"value": it})}
        logger.info(f"[节点] List.ForEach index={idx}")
        if asyncio.iscoroutinefunction(body_executor):
            await body_executor(session, state, params)
        else:
            body_executor(session, state, params)


@register_node("List.ForEachRange")
async def node_list_foreach_range(session: Session, state: dict, params: dict, body_executor):
    """
    List.ForEachRange: 根据计数遍历 1..N
    params:
      - countPath: string 例如 "$.content.stage_count"
      - start: int 默认 1
    """
    count_path = params.get("countPath")
    if not isinstance(count_path, str):
        logger.warning("[节点] List.ForEachRange 缺少 countPath")
        return
    card = state.get("card") or (state.get("current") or {}).get("card")
    base = {"content": getattr(card, "content", {})} if card else {}
    count_val = _get_by_path({"$": base}, count_path) or 0
    try:
        n = int(count_val)
    except Exception:
        n = 0
    
    if n <= 0:
        logger.info(f"[节点] List.ForEachRange 计数为 {n}，跳过循环")
        return
    
    start = int(params.get("start", 1) or 1)
    for i in range(start, start + n):
        state["item"] = {"index": i}
        logger.info(f"[节点] List.ForEachRange index={i} (共{n}次)")
        if asyncio.iscoroutinefunction(body_executor):
            await body_executor(session, state, params)
        else:
            body_executor(session, state, params)


@register_node("Card.ClearFields")
def node_card_clear_fields(session: Session, state: Dict[str, Any], params: Dict[str, Any]) -> None:
    """
    Card.ClearFields: 清空卡片的指定字段
    参数:
    - target: 目标卡片 ID 或 '$self'
    - fields: 要清空的字段路径列表 (如 ['$.content.field1', '$.content.field2'])
    """
    target = params.get("target", "$self")
    fields = params.get("fields", [])
    
    if target == "$self":
        target_id = state["scope"].get("card_id")
    else:
        target_id = int(target) if isinstance(target, (int, str)) and str(target).isdigit() else None
    
    if not target_id:
        logger.warning(f"[Card.ClearFields] 无效的目标卡片: {target}")
        return
        
    card = _get_card_by_id(session, target_id)
    if not card:
        logger.warning(f"[Card.ClearFields] 卡片不存在: {target_id}")
        return
    
    if not isinstance(fields, list) or not fields:
        logger.warning("[Card.ClearFields] 缺少有效的 fields 参数")
        return
    
    # 使用深拷贝避免修改原始对象
    content = copy.deepcopy(card.content or {})
    
    # 清空指定字段
    for field_path in fields:
        if isinstance(field_path, str) and field_path.startswith("$."):
            _set_by_path({"$": content}, field_path, None)
    
    card.content = content
    session.add(card)
    session.commit()
    
    # 记录受影响的卡片
    if "touched_card_ids" in state:
        state["touched_card_ids"].add(target_id)


@register_node("Card.ReplaceFieldText")
def node_card_replace_field_text(session: Session, state: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Card.ReplaceFieldText: 替换卡片字段中的指定文本片段
    
    参数:
    - card_id: 目标卡片ID
    - field_path: 字段路径（如 "content", "overview" 等）
    - old_text: 要被替换的原文片段（必须完全匹配）
    - new_text: 新的文本内容
    
    返回:
    - success: 是否成功
    - replaced_count: 替换次数
    - old_length: 原文本长度
    - new_length: 新文本长度
    - error: 错误信息（如果失败）
    """
    card_id = params.get("card_id")
    field_path = params.get("field_path", "")
    old_text = params.get("old_text", "")
    new_text = params.get("new_text", "")
    
    if not card_id:
        return {"success": False, "error": "缺少 card_id 参数"}
    
    if not field_path:
        return {"success": False, "error": "缺少 field_path 参数"}
    
    if not old_text:
        return {"success": False, "error": "缺少 old_text 参数"}
    
    # 获取卡片
    card = _get_card_by_id(session, int(card_id))
    if not card:
        return {"success": False, "error": f"卡片 {card_id} 不存在"}
    
    # 处理字段路径，标准化为 content. 前缀
    normalized_path = field_path
    if not normalized_path.startswith("content."):
        normalized_path = f"content.{normalized_path}"
    
    logger.info(f"  原始字段路径: {field_path}")
    logger.info(f"  标准化路径: {normalized_path}")
    
    # 获取字段当前值
    path_parts = normalized_path.split(".")
    logger.info(f"  路径分段: {path_parts}")
    
    current_value = card.content or {}
    logger.info(f"  card.content 类型: {type(current_value)}")
    logger.info(f"  card.content 键: {list(current_value.keys()) if isinstance(current_value, dict) else 'N/A'}")
    
    # 逐层访问到目标字段
    for i, part in enumerate(path_parts[1:]):  # 跳过 "content"
        logger.info(f"  访问层级 {i+1}: 字段 '{part}', 当前值类型 {type(current_value)}")
        if isinstance(current_value, dict):
            current_value = current_value.get(part, "")
            logger.info(f"    获取到的值长度: {len(str(current_value))}")
        else:
            return {
                "success": False,
                "error": f"字段路径 {normalized_path} 无效（在 {part} 处不是字典）"
            }
    
    # 确保当前值是字符串
    if not isinstance(current_value, str):
        return {
            "success": False,
            "error": f"字段 {field_path} 不是文本类型，无法进行文本替换"
        }
    
    # 检查是否使用模糊匹配模式（开头...结尾）
    fuzzy_match = False
    actual_old_text = old_text
    
    if "..." in old_text or "……" in old_text:
        # 模糊匹配模式：提取开头和结尾
        fuzzy_match = True
        separator = "..." if "..." in old_text else "……"
        parts = old_text.split(separator, 1)  # 只分割一次
        
        if len(parts) == 2:
            start_text = parts[0].strip()
            end_text = parts[1].strip()
            
            logger.info(f"  🔍 使用模糊匹配模式")
            logger.info(f"  开头文本: {start_text[:20]}...")
            logger.info(f"  结尾文本: ...{end_text[-20:]}")
            
            # 在内容中查找匹配的片段
            start_idx = current_value.find(start_text)
            if start_idx == -1:
                return {
                    "success": False,
                    "error": f"在字段 '{field_path}' 中未找到开头文本: {start_text[:30]}...",
                    "hint": "请确认开头文本是否完全匹配"
                }
            
            # 从开头位置之后查找结尾
            end_search_start = start_idx + len(start_text)
            end_idx = current_value.find(end_text, end_search_start)
            if end_idx == -1:
                return {
                    "success": False,
                    "error": f"在字段 '{field_path}' 中未找到结尾文本: ...{end_text[-30:]}",
                    "hint": "请确认结尾文本是否完全匹配"
                }
            
            # 提取完整的匹配片段
            actual_old_text = current_value[start_idx:end_idx + len(end_text)]
            logger.info(f"  ✅ 模糊匹配成功，找到 {len(actual_old_text)} 字符的片段")
        else:
            return {
                "success": False,
                "error": "模糊匹配格式错误，应为：开头文本...结尾文本",
                "hint": "使用三个点或六个点作为分隔符"
            }
    
    # 检查原文是否存在（精确匹配或模糊匹配后的完整文本）
    if actual_old_text not in current_value:
        preview = current_value[:100] + "..." if len(current_value) > 100 else current_value
        error_message = f"在字段 '{field_path}' 中未找到指定的原文片段"
        logger.warning(f"⚠️ 文本未找到，field_path='{field_path}'")
        return {
            "success": False,
            "error": error_message,
            "field_preview": preview,
            "hint": "请确认原文片段是否完全匹配（包括标点符号和空格、换行符）"
        }
    
    # 执行替换
    replaced_count = current_value.count(actual_old_text)
    updated_value = current_value.replace(actual_old_text, new_text)
    
    if fuzzy_match:
        logger.info(f"  📝 模糊匹配替换: 原文 {len(actual_old_text)} 字符 → 新文本 {len(new_text)} 字符")
    
    logger.info(f"[Card.ReplaceFieldText] card_id={card_id}, field={field_path}, 找到 {replaced_count} 处匹配")
    logger.info(f"  替换前长度: {len(current_value)} 字符")
    logger.info(f"  替换后长度: {len(updated_value)} 字符")
    
    # 使用深拷贝避免修改原始对象
    content = copy.deepcopy(card.content or {})
    
    # 设置更新后的值
    # 去掉 "content." 前缀，得到实际的字段路径
    field_parts = normalized_path.split(".")[1:]  # 去掉 "content"，得到 ["field"] 或 ["nested", "field"]
    
    # 逐层访问并设置值
    current_dict = content
    for part in field_parts[:-1]:
        if part not in current_dict:
            current_dict[part] = {}
        current_dict = current_dict[part]
    
    # 设置最终字段的值
    current_dict[field_parts[-1]] = updated_value
    
    card.content = content
    session.add(card)
    session.commit()
    session.refresh(card)
    
    # 记录受影响的卡片
    if "touched_card_ids" in state:
        state["touched_card_ids"].add(int(card_id))
    
    logger.info(f"[Card.ReplaceFieldText] 替换成功")
    
    return {
        "success": True,
        "card_id": card_id,
        "card_title": card.title,
        "field_path": field_path,
        "replaced_count": replaced_count,
        "old_length": len(current_value),
        "new_length": len(updated_value)
    }


# ==================== AI & Context 节点 ====================

@register_node("LLM.Generate")
async def node_llm_generate(session: Session, state: dict, params: dict) -> dict:
    """
    LLM.Generate: 调用 AI 生成内容
    params:
      - prompt: 提示词模板
      - targetPath: 结果写入 state 的路径 (默认 "$.last_ai_response")
      - model: 模型名称 (可选)
      - temperature: 温度 (可选)
      - style: 写作风格指引 (可选)
    """
    # 获取 LLM 配置
    configs = llm_config_service.get_llm_configs(session)
    llm_config_id = configs[0].id if configs else 1
    
    prompt_tpl = params.get("prompt", "")
    final_prompt = _render_value(prompt_tpl, state)
    
    temperature = params.get("temperature")
    style = _render_value(params.get("style"), state)
    
    logger.info(f"[节点] LLM.Generate 开始生成...")

    from app.schemas.ai import ContinuationResponse
    result = await agent_service.run_llm_agent(
        session=session,
        llm_config_id=llm_config_id,
        user_prompt=final_prompt,
        output_type=ContinuationResponse,
        temperature=temperature,
        style_guidelines=style
    )
    
    content = result.content if hasattr(result, "content") else str(result)
    target_path = params.get("targetPath", "$.last_ai_response")
    
    # 写入 state
    _set_by_path(state, target_path, content)
    
    return {"content": content, "raw_result": result}


@register_node("Context.Assemble")
def node_context_assemble(session: Session, state: dict, params: dict) -> dict:
    """
    Context.Assemble: 装配上下文（事实、关系等）
    params:
      - participants: 参与者列表 (可选)
      - max_chapter_id: 最大章节ID (用于时间切片)
      - radius: 查询半径 (可选)
      - top_k: 最大返回事实数 (可选)
      - pov_character: 主观视角角色 (可选)
    """
    from app.services import context_service
    from app.services.context_service import ContextAssembleParams
    
    project_id = state.get("scope", {}).get("project_id")
    participants = _render_value(params.get("participants", []), state)
    max_chapter_id = _render_value(params.get("max_chapter_id"), state)
    radius = _render_value(params.get("radius"), state)
    top_k = _render_value(params.get("top_k"), state)
    pov_character = _render_value(params.get("pov_character"), state)
    
    assemble_params = ContextAssembleParams(
        project_id=project_id,
        participants=participants,
        chapter_id=max_chapter_id,
        radius=radius,
        top_k=top_k,
        pov_character=pov_character,
    )
    
    from dataclasses import asdict
    context = context_service.assemble_context(session, assemble_params)
    
    state["assembled_context"] = asdict(context)
    
    return {"context": context}


@register_node("Tools.ParseJSON")
def node_tools_parse_json(session: Session, state: dict, params: dict) -> dict:
    """
    Tools.ParseJSON: 解析 JSON 字符串为对象
    params:
      - sourcePath: 源字符串路径 (如 "$.last_ai_response")
      - targetPath: 结果写入路径 (如 "$.parsed_data")
    """
    import json
    
    source_path = params.get("sourcePath", "$.last_ai_response")
    target_path = params.get("targetPath", "$.parsed_data")
    
    source_val = _get_from_state(source_path, state)
    if not isinstance(source_val, str):
        logger.warning(f"[节点] Tools.ParseJSON 源数据非字符串: {type(source_val)}")
        return {"success": False}
    
    try:
        # 尝试提取 JSON 块（处理 AI 可能带有的 Markdown 标签）
        json_match = re.search(r"```json\s*(.*?)\s*```", source_val, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = source_val
            
        data = json.loads(json_str)
        _set_by_path(state, target_path, data)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"[节点] Tools.ParseJSON 失败: {e}")
        return {"success": False, "error": str(e)}


@register_node("Audit.Consistency")
async def node_audit_consistency(session: Session, state: dict, params: dict) -> dict:
    """
    Audit.Consistency: 检查内容一致性
    params:
      - sourcePath: 待检查内容路径 (默认 "$.current.card.content")
      - targetPath: 结果写入路径 (默认 "$.audit_result")
      - promptName: 提示词名称 (默认 "一致性检查")
    """
    from app.services import agent_service
    
    source_path = params.get("sourcePath", "$.current.card.content")
    target_path = params.get("targetPath", "$.audit_result")
    prompt_name = params.get("promptName", "一致性检查")
    
    content = _get_from_state(source_path, state)
    if isinstance(content, dict):
        # 如果是字典，尝试取正文或转为字符串
        content = content.get("content") or content.get("text") or str(content)
    
    # 获取上下文（如果之前执行了 Context.Assemble）
    context_data = state.get("assembled_context") or {}
    facts_subgraph = context_data.get("facts_subgraph", "暂无参考事实。")
    
    user_prompt = f"### 待检查内容\n{content}\n\n### 参考上下文\n{facts_subgraph}"
    
    logger.info(f"[节点] Audit.Consistency 开始审计...")
    
    # 获取 LLM 配置
    configs = llm_config_service.get_llm_configs(session)
    llm_config_id = configs[0].id if configs else 1
    
    # 获取提示词
    prompt = prompt_service.get_prompt_by_name(session, prompt_name)
    system_prompt = prompt.template if prompt else "你是一个专业的小说审计助手。"

    # 定义输出结构
    class AuditResult(BaseModel):
        has_issues: bool
        issues: List[dict]

    result = await agent_service.run_llm_agent(
        session=session,
        llm_config_id=llm_config_id,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        output_type=AuditResult
    )
    
    # 写入 state
    _set_by_path(state, target_path, result.model_dump() if hasattr(result, "model_dump") else result)
    
    return {"result": result}


@register_node("KG.UpdateFromContent")
async def node_kg_update_from_content(session: Session, state: dict, params: dict) -> dict:
    """
    KG.UpdateFromContent: 从内容中提取事实并更新知识图谱
    params:
      - sourcePath: 待提取内容路径 (默认 "$.current.card.content")
      - participants: 参与者列表 (可选)
    """
    from app.services.memory_service import MemoryService
    from app.schemas.memory import ParticipantTyped
    
    source_path = params.get("sourcePath", "$.current.card.content")
    content = _get_from_state(source_path, state)
    if isinstance(content, dict):
        content = content.get("content") or content.get("text") or str(content)
        
    participants_raw = _render_value(params.get("participants", []), state) or []
    participants = []
    for p in participants_raw:
        if isinstance(p, str):
            participants.append(ParticipantTyped(name=p, type="character"))
        elif isinstance(p, dict):
            participants.append(ParticipantTyped(**p))
            
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("KG.UpdateFromContent 缺少 project_id")
        
    memory_svc = MemoryService(session)
    
    logger.info(f"[节点] KG.UpdateFromContent 开始提取并更新...")
    
    # 获取 LLM 配置
    configs = llm_config_service.get_llm_configs(session)
    llm_config_id = configs[0].id if configs else 1

    # 1. 提取关系
    extraction = await memory_svc.extract_relations_llm(
        text=content,
        participants=participants,
        llm_config_id=llm_config_id
    )
    
    # 2. 写入图谱
    result = memory_svc.ingest_relations_from_llm(
        project_id=project_id,
        data=extraction,
        participants_with_type=participants
    )
    
    # 3. 提取并更新动态信息
    dynamic_info = await memory_svc.extract_dynamic_info_from_text(
        text=content,
        participants=participants,
        llm_config_id=llm_config_id,
        project_id=project_id
    )
    memory_svc.update_dynamic_character_info(project_id, dynamic_info)
    
    return {"extraction": extraction, "ingest_result": result, "dynamic_info": dynamic_info}

@register_node("Tools.Wait")
async def node_tools_wait(session: Session, state: dict, params: dict) -> dict:
    """
    Tools.Wait: 等待指定时间或手动恢复
    params:
      - seconds: 等待秒数 (可选)
      - message: 等待时显示的消息 (可选)
    """
    seconds = params.get("seconds")
    message = params.get("message", "等待中...")
    
    logger.info(f"[节点] Tools.Wait: {message}")
    
    if seconds:
        await asyncio.sleep(float(seconds))
        return {"waited": seconds}
    
    # 如果没有指定秒数，则视为一个断点，需要外部恢复（目前仅记录日志）
    logger.warning(f"[节点] Tools.Wait 断点触发: {message}")
    return {"breakpoint": True}


@register_node("Style.Assemble")
def node_style_assemble(session: Session, state: dict, params: dict) -> dict:
    """
    Style.Assemble: 从卡片中装配写作风格
    params:
      - styleCardTitle: 风格卡片的标题 (默认 "写作风格")
      - targetPath: 结果写入路径 (默认 "$.current_style")
    """
    project_id = state.get("scope", {}).get("project_id")
    style_card_title = _render_value(params.get("styleCardTitle", "写作风格"), state)
    target_path = params.get("targetPath", "$.current_style")
    
    if not project_id:
        return {"success": False, "error": "Missing project_id"}
        
    # 查询风格卡片
    from app.db.models import Card
    stmt = select(Card).where(Card.project_id == project_id, Card.title == style_card_title)
    card = session.exec(stmt).first()
    
    if not card:
        logger.warning(f"[节点] Style.Assemble 未找到风格卡片: {style_card_title}")
        return {"success": False, "error": "Style card not found"}
        
    style_content = card.content or ""
    _set_by_path(state, target_path, style_content)
    
    return {"success": True, "style": style_content}


@register_node("Card.Delete")
def node_card_delete(session: Session, state: dict, params: dict) -> dict:
    """
    Card.Delete: 删除锚点卡片或指定 card_id
    params:
      - target: "$self" | int(card_id)
    """
    target = params.get("target", "$self")
    
    card_id: Optional[int] = None
    if target == "$self":
        scope = state.get("scope") or {}
        card_id = scope.get("card_id")
    else:
        try:
            card_id = int(target)
        except Exception:
            card_id = None
    
    if not card_id:
        raise ValueError("Card.Delete 未指定有效的卡片 ID")
    
    from app.services.card_service import CardService
    service = CardService(session)
    success = service.delete(card_id)
    
    if not success:
        logger.warning(f"[节点] 删除卡片失败，未找到 card_id={card_id}")
        return {"success": False, "error": "Card not found"}
    
    logger.info(f"[节点] 删除卡片成功 card_id={card_id}")
    
    # 如果删除的是当前 state 中的卡片，清除引用
    if state.get("card") and state["card"].id == card_id:
        state["card"] = None
    if state.get("current") and state["current"].get("card") and state["current"]["card"].id == card_id:
        state["current"]["card"] = None
        
    return {"success": True, "card_id": card_id}


@register_node("CardTemplate.Apply")
def node_card_template_apply(session: Session, state: dict, params: dict) -> dict:
    """
    CardTemplate.Apply: 应用卡片模板到指定卡片
    params:
      - templateId: 模板 ID
      - target: "$self" | int(card_id)
    """
    template_id = params.get("templateId")
    target = params.get("target", "$self")
    
    if not template_id:
        raise ValueError("CardTemplate.Apply 未指定 templateId")
        
    from app.services.card_template_service import CardTemplateService
    from app.services.card_service import CardService
    from app.schemas.card import CardUpdate
    
    template_svc = CardTemplateService(session)
    card_svc = CardService(session)
    
    template = template_svc.get_by_id(int(template_id))
    if not template:
        return {"success": False, "error": "Template not found"}
        
    card_id: Optional[int] = None
    if target == "$self":
        scope = state.get("scope") or {}
        card_id = scope.get("card_id")
    else:
        try:
            card_id = int(target)
        except Exception:
            card_id = None
            
    if not card_id:
        raise ValueError("CardTemplate.Apply 未指定有效的卡片 ID")
        
    card = card_svc.get_by_id(card_id)
    if not card:
        return {"success": False, "error": "Card not found"}
        
    # 应用模板内容
    card_update = CardUpdate(content=template.content)
    updated_card = card_svc.update(card_id, card_update)
    
    return {"success": True, "card_id": card_id, "template_id": template_id}


@register_node("Outline.Generate")
async def node_outline_generate(session: Session, state: dict, params: dict) -> dict:
    """
    Outline.Generate: 为章节生成梗概并同步到大纲卡片
    params:
      - sourcePath: 章节内容路径 (默认 "$.content.content")
      - targetCardType: 大纲卡片类型 (默认 "章节大纲")
    """
    source_path = params.get("sourcePath", "$.content.content")
    content = _get_from_state(source_path, state)
    if isinstance(content, dict):
        content = content.get("content") or content.get("text") or str(content)
    
    if not content or len(str(content).strip()) < 10:
        return {"success": False, "error": "Content too short or empty"}

    project_id = state.get("scope", {}).get("project_id")
    card_id = state.get("scope", {}).get("card_id")
    if not project_id or not card_id:
        raise ValueError("Outline.Generate 缺少 project_id 或 card_id")

    # 1. 获取 LLM 配置
    configs = llm_config_service.get_llm_configs(session)
    llm_config_id = configs[0].id if configs else 1

    # 2. 调用 LLM 生成梗概
    class OutlineResult(BaseModel):
        summary: str

    user_prompt = f"请为以下小说章节内容生成一段简洁的梗概（200-500字），重点描述核心情节和转折：\n\n{content}"
    system_prompt = "你是一个专业的小说编辑，擅长提炼章节大纲。"

    result = await agent_service.run_llm_agent(
        session=session,
        llm_config_id=llm_config_id,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        output_type=OutlineResult
    )

    summary = result.summary

    # 3. 查找或创建大纲卡片
    from app.services.card_service import CardService
    from app.schemas.card import CardCreate, CardUpdate
    card_svc = CardService(session)
    
    current_card = card_svc.get_by_id(card_id)
    if not current_card:
        return {"success": False, "error": "Current card not found"}

    target_type_name = params.get("targetCardType", "章节大纲")
    ct = session.exec(select(CardType).where(CardType.name == target_type_name)).first()
    if not ct:
        return {"success": False, "error": f"Card type {target_type_name} not found"}

    # 查找同父级下同名的大纲卡片
    stmt = select(Card).where(
        Card.project_id == project_id,
        Card.parent_id == current_card.parent_id,
        Card.card_type_id == ct.id,
        Card.title == current_card.title
    )
    outline_card = session.exec(stmt).first()

    if outline_card:
        card_svc.update(outline_card.id, CardUpdate(content={"content": summary}))
    else:
        card_svc.create(CardCreate(
            title=current_card.title,
            project_id=project_id,
            parent_id=current_card.parent_id,
            card_type_id=ct.id,
            content={"content": summary},
            display_order=current_card.display_order
        ))

    return {"success": True, "summary": summary}


@register_node("World.Aggregate")
async def node_world_aggregate(session: Session, state: dict, params: dict) -> dict:
    """
    World.Aggregate: 聚合项目中的实体信息，生成/更新世界观设定卡片
    params:
      - targetFolder: 存放设定卡片的文件夹名称 (默认 "世界观设定")
    """
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("World.Aggregate 缺少 project_id")

    from app.services.memory_service import MemoryService
    memory_svc = MemoryService(session)
    
    # 1. 获取所有实体和关系
    # 这里简化处理：获取最近提取的实体或从 KG 中聚合
    # 实际上我们可以调用 memory_svc 相关的聚合方法
    entities = memory_svc.get_all_entities(project_id)
    if not entities:
        return {"success": False, "error": "No entities found in Knowledge Graph"}

    entity_desc = "\n".join([f"- {e.name} ({e.type}): {e.description or ''}" for e in entities[:50]])

    # 2. 调用 LLM 聚合世界观
    class WorldSetting(BaseModel):
        title: str
        content: str

    class WorldAggregateResult(BaseModel):
        settings: List[WorldSetting]

    user_prompt = f"以下是从小说中提取的实体信息，请根据这些信息归纳并撰写系统的世界观设定（如地理环境、力量体系、势力分布等）：\n\n{entity_desc}"
    system_prompt = "你是一个资深的世界观架构师，擅长从零散信息中构建宏大且严谨的设定系统。"

    configs = llm_config_service.get_llm_configs(session)
    llm_config_id = configs[0].id if configs else 1

    result = await agent_service.run_llm_agent(
        session=session,
        llm_config_id=llm_config_id,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        output_type=WorldAggregateResult
    )

    # 3. 创建/更新设定卡片
    from app.services.card_service import CardService
    from app.schemas.card import CardCreate, CardUpdate
    card_svc = CardService(session)

    # 查找或创建“世界观设定”文件夹
    folder_name = params.get("targetFolder", "世界观设定")
    folder_type = session.exec(select(CardType).where(CardType.name == "文件夹")).first()
    setting_type = session.exec(select(CardType).where(CardType.name == "世界观设定")).first()
    
    if not folder_type or not setting_type:
        return {"success": False, "error": "Required card types (文件夹/世界观设定) not found"}

    stmt = select(Card).where(Card.project_id == project_id, Card.title == folder_name, Card.card_type_id == folder_type.id)
    folder = session.exec(stmt).first()
    if not folder:
        folder = card_svc.create(CardCreate(
            title=folder_name,
            project_id=project_id,
            card_type_id=folder_type.id,
            content={}
        ))

    created_cards = []
    for setting in result.settings:
        # 查找同名设定卡片
        stmt = select(Card).where(
            Card.project_id == project_id,
            Card.parent_id == folder.id,
            Card.title == setting.title,
            Card.card_type_id == setting_type.id
        )
        existing = session.exec(stmt).first()
        if existing:
            card_svc.update(existing.id, CardUpdate(content={"content": setting.content}))
            created_cards.append(existing.id)
        else:
            new_c = card_svc.create(CardCreate(
                title=setting.title,
                project_id=project_id,
                parent_id=folder.id,
                card_type_id=setting_type.id,
                content={"content": setting.content}
            ))
            created_cards.append(new_c.id)

    return {"success": True, "created_card_ids": created_cards}


@register_node("Vector.Ingest")
def node_vector_ingest(session: Session, state: dict, params: dict) -> dict:
    """
    Vector.Ingest: 将文本存入向量数据库
    params:
      - sourcePath: 文本内容路径 (默认 "$.content.content")
      - metadata: dict (可选元数据，如 type, chapter_id)
    """
    from app.services.vector_service import VectorService
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("Vector.Ingest 缺少 project_id")

    source_path = params.get("sourcePath", "$.content.content")
    content = _get_from_state(source_path, state)
    if not content or not isinstance(content, str):
        return {"success": False, "error": "Content is empty or not a string"}

    # 简单的文本切分 (按段落)
    chunks = [c.strip() for c in content.split('\n') if len(c.strip()) > 20]
    if not chunks:
        return {"success": False, "error": "No valid chunks found"}

    metadata_tpl = params.get("metadata", {})
    
    # 渲染元数据
    rendered_meta = {}
    for k, v in metadata_tpl.items():
        rendered_meta[k] = _render_value(v, state)

    # 补充默认元数据
    card_id = state.get("scope", {}).get("card_id")
    if card_id:
        rendered_meta["card_id"] = card_id
    
    ids = [f"{project_id}_{card_id}_{i}" for i in range(len(chunks))]
    metadatas = [rendered_meta] * len(chunks)

    svc = VectorService()
    success = svc.add_texts(project_id, chunks, metadatas, ids)
    
    return {"success": success, "chunk_count": len(chunks)}


@register_node("Vector.Search")
def node_vector_search(session: Session, state: dict, params: dict) -> dict:
    """
    Vector.Search: 语义检索
    params:
      - query: str (检索词)
      - top_k: int (默认 5)
      - filter: dict (可选过滤条件)
      - targetPath: str (结果写入路径，默认 "$.vector_results")
    """
    from app.services.vector_service import VectorService

    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("Vector.Search 缺少 project_id")

    query = params.get("query")
    query = _render_value(query, state)
    if not query:
        return {"success": False, "error": "Query is empty"}

    top_k = params.get("top_k", 5)
    filter_dict = params.get("filter")

    svc = VectorService()
    results = svc.search(project_id, query, top_k, filter_dict)

    target_path = params.get("targetPath", "$.vector_results")
    
    # 写入 state
    # 如果 targetPath 是 $.xxx，直接写入 state[xxx]
    if target_path.startswith("$."):
        key = target_path[2:]
        state[key] = results
    else:
        state[target_path] = results

    return {"success": True, "count": len(results), "results": results}


@register_node("Foreshadow.Extract")
async def node_foreshadow_extract(session: Session, state: dict, params: dict) -> dict:
    """
    Foreshadow.Extract: 自动提取伏笔
    params:
      - sourcePath: str (默认 "$.content.content")
      - autoRegister: bool (是否自动存入数据库，默认 True)
    """
    from app.services.foreshadow_service import ForeshadowService
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("Foreshadow.Extract 缺少 project_id")
        
    source_path = params.get("sourcePath", "$.content.content")
    content = _get_from_state(source_path, state)
    if not content or not isinstance(content, str):
        return {"success": False, "error": "Content is empty"}

    svc = ForeshadowService(session)
    # 异步调用 LLM
    suggestions = await svc.suggest(content)
    
    # 整理结果
    entries = []
    card_id = state.get("scope", {}).get("card_id")
    
    for g in suggestions.get("goals", []):
        entries.append({"title": g, "type": "goal", "chapter_id": card_id, "note": "自动提取的目标"})
    for i in suggestions.get("items", []):
        entries.append({"title": i, "type": "item", "chapter_id": card_id, "note": "自动提取的物品"})
    for p in suggestions.get("persons", []):
        entries.append({"title": p, "type": "person", "chapter_id": card_id, "note": "自动提取的人物"})

    if params.get("autoRegister", True) and entries:
        svc.register(project_id, entries)
        
    state["foreshadow_suggestions"] = suggestions
    return {"success": True, "count": len(entries), "entries": entries}


@register_node("Foreshadow.Check")
async def node_foreshadow_check(session: Session, state: dict, params: dict) -> dict:
    """
    Foreshadow.Check: 检查伏笔回收
    params:
      - sourcePath: str (默认 "$.content.content")
    """
    from app.services.foreshadow_service import ForeshadowService
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("Foreshadow.Check 缺少 project_id")
        
    source_path = params.get("sourcePath", "$.content.content")
    content = _get_from_state(source_path, state)
    if not content or not isinstance(content, str):
        return {"success": False, "error": "Content is empty"}

    svc = ForeshadowService(session)
    resolved_ids = await svc.check_resolution(project_id, content)
    
    resolved_items = []
    if resolved_ids:
        for rid in resolved_ids:
            item = svc.resolve(project_id, rid)
            if item:
                resolved_items.append(item.title)
    
    state["resolved_foreshadows"] = resolved_items
    return {"success": True, "resolved_count": len(resolved_items), "resolved_items": resolved_items}





@register_node("Style.Assemble")
def node_style_assemble(session: Session, state: dict, params: dict) -> dict:
    """
    Style.Assemble: 动态组装文风参考
    params:
      - sourcePath: str (参考内容的来源路径，默认 "$.content.content")
      - top_k: int (检索数量，默认 3)
      - targetPath: str (结果写入路径，默认 "$.style_context")
    """
    from app.services.style_service import StyleService
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("Style.Assemble 缺少 project_id")
        
    source_path = params.get("sourcePath", "$.content.content")
    content_snippet = _get_from_state(source_path, state)
    
    # 如果当前内容为空（如刚开始写），可以使用上一章的结尾，或者留空
    if not content_snippet or not isinstance(content_snippet, str):
        content_snippet = ""
        
    top_k = params.get("top_k", 3)
    
    svc = StyleService()
    styles = svc.retrieve_relevant_styles(project_id, content_snippet, top_k)
    
    style_text = ""
    if styles:
        style_text = "请模仿以下项目既有文风进行写作：\n" + "\n---\n".join(styles)
        
    target_path = params.get("targetPath", "$.style_context")
    if target_path.startswith("$."):
        key = target_path[2:]
        state[key] = style_text
    else:
        state[target_path] = style_text
        
    return {"success": True, "count": len(styles), "style_text_len": len(style_text)}

@register_node("KG.UpdateFromContent")
async def node_kg_update_from_content(session: Session, state: dict, params: dict) -> dict:
    """
    KG.UpdateFromContent: 从内容中提取事实并更新知识图谱
    params:
      - sourcePath: str (默认 "$.content.content")
      - participants: list[str] (参与者列表，用于聚焦提取)
    """
    from app.services.relation_service import RelationService
    from app.services.kg_provider import get_provider
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("KG.UpdateFromContent 缺少 project_id")
        
    source_path = params.get("sourcePath", "$.content.content")
    content = _get_from_state(source_path, state)
    if not content or not isinstance(content, str):
        return {"success": False, "error": "Content is empty"}
        
    participants = params.get("participants")
    if isinstance(participants, str):
        participants = _render_value(participants, state)
        if isinstance(participants, str):
            # 尝试解析 JSON 或逗号分隔
            try:
                import json
                participants = json.loads(participants)
            except:
                participants = [p.strip() for p in participants.split(",") if p.strip()]
                
    # 1. 提取关系
    svc = RelationService(session)
    triples = svc.extract_from_text(content, participants)
    
    # 2. 写入图谱
    kg = get_provider()
    
    kg_triples = []
    for t in triples:
        s = t.get("subject")
        p = t.get("predicate")
        o = t.get("object")
        attrs = t.get("attributes", {})
        
        if s and p and o:
            kg_triples.append((s, p, o, attrs))
            
    if kg_triples:
        kg.ingest_triples_with_attributes(project_id, kg_triples)
        
    return {"success": True, "count": len(kg_triples)}


@register_node("World.Aggregate")
async def node_world_aggregate(session: Session, state: dict, params: dict) -> dict:
    """
    World.Aggregate: 世界观深度归纳
    params:
      - targetFolder: str (目标文件夹名称，默认 "世界观设定")
    """
    from app.services.kg_provider import get_provider
    from app.services.llm_factory import LLMFactory
    from app.services.card_service import CardService
    from app.schemas.card import CardCreate, CardUpdate
    from app.models.card import Card, CardType
    from sqlmodel import select
    
    project_id = state.get("scope", {}).get("project_id")
    if not project_id:
        raise ValueError("World.Aggregate 缺少 project_id")
        
    # 1. 获取全量图谱事实
    kg = get_provider()
    graph_data = kg.get_full_graph(project_id)
    
    # 简化事实列表，仅保留 fact 字段
    facts = []
    for edge in graph_data.get("edges", []):
        props = edge.get("properties", {})
        if props.get("fact"):
            facts.append(props["fact"])
            
    if not facts:
        return {"success": False, "error": "No facts found in Knowledge Graph"}
        
    # 2. 调用 LLM 进行归纳
    # 由于事实可能很多，这里可能需要分批或摘要，暂且假设 LLM 上下文足够
    facts_text = "\n".join(facts[:500]) # 限制数量以防溢出
    
    prompt = f"""
    请分析以下小说中的事实片段，归纳出该小说的世界观设定。
    请将设定分为以下几类：
    1. 魔法/力量体系
    2. 地理/势力分布
    3. 历史/神话传说
    4. 社会/文化习俗
    
    事实片段：
    {facts_text}
    
    请以 JSON 格式返回，Key 为分类名称，Value 为详细的 Markdown 描述。
    示例：
    {{
        "魔法体系": "...",
        "地理分布": "..."
    }}
    """
    
    llm = LLMFactory.get_project_llm(project_id)
    response = await llm.achat(prompt)
    
    import json
    try:
        # 尝试提取 JSON
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end != -1:
            json_str = response[start:end]
            settings_map = json.loads(json_str)
        else:
            settings_map = {"未分类设定": response}
    except:
        settings_map = {"未分类设定": response}
        
    # 3. 创建/更新设定卡片
    card_svc = CardService(session)
    target_folder_name = params.get("targetFolder", "世界观设定")
    
    # 查找文件夹类型
    folder_type = session.exec(select(CardType).where(CardType.name == "文件夹")).first()
    setting_type = session.exec(select(CardType).where(CardType.name == "世界观设定")).first()
    
    if not folder_type or not setting_type:
        return {"success": False, "error": "Card types missing"}
        
    # 查找或创建文件夹
    folder = session.exec(select(Card).where(Card.project_id == project_id, Card.title == target_folder_name, Card.card_type_id == folder_type.id)).first()
    if not folder:
        folder = card_svc.create(CardCreate(
            title=target_folder_name,
            project_id=project_id,
            card_type_id=folder_type.id,
            content={}
        ))
        
    created_count = 0
    for title, content in settings_map.items():
        # 查找同名卡片
        existing = session.exec(select(Card).where(
            Card.project_id == project_id,
            Card.parent_id == folder.id,
            Card.title == title,
            Card.card_type_id == setting_type.id
        )).first()
        
        if existing:
            card_svc.update(existing.id, CardUpdate(content={"content": content}))
        else:
            card_svc.create(CardCreate(
                title=title,
                project_id=project_id,
                parent_id=folder.id,
                card_type_id=setting_type.id,
                content={"content": content}
            ))
        created_count += 1
        
    return {"success": True, "created_count": created_count, "settings": list(settings_map.keys())}
