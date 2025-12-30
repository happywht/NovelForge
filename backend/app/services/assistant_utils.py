import json
import re
from typing import Any, Dict, Optional, Tuple, List

from loguru import logger
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from app.services.assistant_tools.ai_tools import ASSISTANT_TOOL_DESCRIPTIONS

_ACTION_TAG_RE = re.compile(r"<Action>(.*?)</Action>", re.IGNORECASE | re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"Action\s*:?\s*(\{.*\})", re.IGNORECASE | re.DOTALL)
_PROTOCOL_TAGS = ("action",)

def _extract_first(pattern: re.Pattern, text: str) -> Optional[str]:
    if not text:
        return None
    m = pattern.search(text)
    if not m:
        return None
    return (m.group(1) or "").strip()


def _clean_code_fence(block: str) -> str:
    if not block:
        return ""
    fence = _CODE_FENCE_RE.search(block)
    if fence:
        return fence.group(1).strip()
    return block.strip()


def _parse_action_payload(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    if not text:
        return None

    raw_block = _extract_first(_ACTION_TAG_RE, text)
    if not raw_block:
        raw_block = _extract_first(_JSON_BLOCK_RE, text)
    if not raw_block:
        return None

    cleaned = _clean_code_fence(raw_block)
    candidate = cleaned
    try:
        data = json.loads(candidate)
    except Exception:
        try:
            candidate = cleaned.replace("'", '"')
            data = json.loads(candidate)
        except Exception:
            logger.debug(f"[React Parser] JSON 解析失败: {cleaned}")
            return None

    if not isinstance(data, dict):
        return None

    tool_name = (
        data.get("tool")
        or data.get("tool_name")
        or data.get("name")
        or data.get("action")
    )

    if not isinstance(tool_name, str) or not tool_name.strip():
        return None

    args = (
        data.get("input")
        or data.get("args")
        or data.get("parameters")
        or {}
    )

    if args is None:
        args = {}

    if not isinstance(args, dict):
        try:
            args = dict(args)
        except Exception:
            logger.debug(f"[React Parser] 工具参数无法转换为 dict: {args}")
            return None

    return tool_name.strip(), args


def _process_react_stream_text(state: dict[str, str], new_text: str) -> str:
    """在流式阶段移除协议标签，但保留换行符和空白字符以维护 Markdown 格式。"""

    buffer = state.get("buffer", "") + (new_text or "")
    output_parts: list[str] = []

    while buffer:
        # 1. 查找最左边的 '<'
        tag_start = buffer.find("<")
        
        # Case A: 没有 '<'，全是安全文本
        if tag_start == -1:
            output_parts.append(buffer)
            buffer = ""
            break
            
        # 先把 '<' 之前的文本输出（保留原始格式）
        if tag_start > 0:
            output_parts.append(buffer[:tag_start])
            buffer = buffer[tag_start:]
            # buffer 现在以 '<' 开头
            
        # 2. 检查这个 '<' 是否是协议标签的开始
        lower = buffer.lower()
        
        potential_tag = None
        for tag in _PROTOCOL_TAGS:
            prefix = f"<{tag}"
            
            if lower.startswith(prefix):
                potential_tag = tag
                break
            # 检查是否是部分匹配（buffer 比标签名短，且完全匹配前缀）
            if len(buffer) < len(prefix) and prefix.startswith(lower):
                # 可能是标签的一部分，等待更多数据
                state["buffer"] = buffer
                return "".join(output_parts)

        # Case B: 看起来完全不是任何已知标签的前缀
        if not potential_tag:
            # 这只是个普通的 '<'，输出它，然后继续处理后面的字符
            output_parts.append("<")
            buffer = buffer[1:]
            continue
            
        # Case C: 确定是某个协议标签（或其前缀）
        close_token = f"</{potential_tag}>"
        close_idx = lower.find(close_token)
        
        if close_idx == -1:
            # 还没收到闭合标签，挂起等待
            state["buffer"] = buffer
            return "".join(output_parts)
            
        # 找到了完整标签块
        block_end = close_idx + len(close_token)
        block = buffer[:block_end]
        
        # 提取内容
        inner_start = block.find(">")
        if inner_start == -1:
            state["buffer"] = buffer
            return "".join(output_parts)
             
        # 提取标签内部内容（目前仅用于完整跳过 <Action> ... </Action>）
        # 注意：这里不直接拼接任何协议标签内部的文本，保证前端只看到清洗后的可见正文。
        _ = block[inner_start + 1 : close_idx]
        
        # 推进 buffer
        buffer = buffer[block_end:]

    state["buffer"] = buffer
    return "".join(output_parts)


def _flush_react_stream_state(state: dict[str, str]) -> str:
    """在对话结束前清空缓冲，防止残留协议文本。"""

    buffer = state.get("buffer", "")
    state["buffer"] = ""
    if not buffer:
        return ""
    return _process_react_stream_text(state, "")


def _render_tool_catalog() -> str:
    lines: list[str] = []
    for name, meta in ASSISTANT_TOOL_DESCRIPTIONS.items():
        desc_raw = meta.get("description") if isinstance(meta, dict) else ""
        desc = (desc_raw or "").strip() or "(无描述)"
        args_meta = meta.get("args") if isinstance(meta, dict) else None
        arg_names: list[str] = []
        if isinstance(args_meta, dict):
            arg_names = [str(key) for key in args_meta.keys()]
        elif isinstance(args_meta, (list, tuple, set)):
            arg_names = [str(item) for item in args_meta]
        elif args_meta:
            arg_names = [str(args_meta)]
        args_text = ", ".join(arg_names) if arg_names else "无参数"
        lines.append(f"- {name}: {desc}（参数: {args_text}）")
    return "\n".join(lines)


def _format_react_user_prompt(context_info: str, user_prompt: str) -> str:
    parts = []
    if context_info:
        parts.append(context_info)
    if user_prompt:
        parts.append(f"用户输入：\n{user_prompt}")
    tool_catalog = _render_tool_catalog()
    if tool_catalog:
        parts.append("可用工具列表：\n" + tool_catalog)
    return "\n\n".join(parts)


def _render_response_text(response: AIMessage) -> str:
    if not response:
        return ""
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
        return "".join(texts)
    return str(content)


def _extract_chunk_parts(chunk: AIMessageChunk) -> Tuple[str, str]:
    """从 AIMessageChunk 中提取正文和思考内容。"""
    text = ""
    reasoning = ""
    
    content = chunk.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            p_type = part.get("type")
            if p_type == "text":
                text += part.get("text", "")
            elif p_type == "reasoning":
                reasoning += part.get("reasoning", "") or part.get("text", "")
    
    # 某些模型可能将 reasoning 放在 additional_kwargs 中
    if not reasoning:
        reasoning = chunk.additional_kwargs.get("reasoning_content", "") or chunk.additional_kwargs.get("thought", "")
        
    return text, reasoning


def _chunk_to_message(chunk: Optional[AIMessageChunk], fallback_text: str) -> AIMessage:
    if chunk:
        return AIMessage(content=chunk.content, tool_calls=chunk.tool_calls, additional_kwargs=chunk.additional_kwargs)
    return AIMessage(content=fallback_text)


def _extract_usage_from_chunk(chunk: AIMessageChunk) -> Optional[Dict[str, Any]]:
    """尝试从 chunk 中提取 usage 信息。"""
    usage = chunk.usage_metadata
    if usage:
        return usage
    
    # 回退：检查 additional_kwargs
    usage = chunk.additional_kwargs.get("usage") or chunk.additional_kwargs.get("token_usage")
    if isinstance(usage, dict):
        return usage
        
    return None
