from typing import Optional
from loguru import logger
from sqlmodel import Session

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_qwq import ChatQwen

from app.db.models import LLMConfig
from app.services import llm_config_service

def _get_llm_config(session: Session, llm_config_id: int) -> Optional[LLMConfig]:
    return llm_config_service.get_llm_config(session, llm_config_id)

def build_chat_model(
    session: Session,
    llm_config_id: int,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    thinking_enabled: Optional[bool] = None,
):
    """
    从LLMConfig创建一个LangChain ChatModel。

    只使用一个小而稳定的初始化参数子集来避免版本特定问题。
    """
    config = _get_llm_config(session, llm_config_id)
    if not config:
        raise ValueError(f"LLM 配置不存在: {llm_config_id}")

    provider = (config.provider or "").lower()
    model_name = config.model_name
    api_key = config.api_key
    api_base = config.api_base

    # 默认参数
    kwargs = {
        "model": model_name,
        "temperature": temperature if temperature is not None else 0.7,
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if timeout:
        kwargs["timeout"] = timeout

    logger.info(f"[LLMFactory] 构建模型: provider={provider}, model={model_name}, timeout={timeout}")

    if provider == "openai":
        return ChatOpenAI(api_key=api_key, base_url=api_base, **kwargs)

    elif provider == "anthropic":
        # Anthropic 的 base_url 映射到 base_url
        return ChatAnthropic(api_key=api_key, base_url=api_base, **kwargs)

    elif provider == "google":
        # Google Generative AI (Gemini)
        return ChatGoogleGenerativeAI(google_api_key=api_key, **kwargs)

    elif provider == "qwen":
        # 阿里通义千问 (DashScope)
        return ChatQwen(api_key=api_key, **kwargs)

    elif provider in ("openai_compatible", "deepseek", "zhipu", "zhipu_anthropic"):
        # 兼容 OpenAI 接口的服务商
        return ChatOpenAI(api_key=api_key, base_url=api_base, **kwargs)

    else:
        # 默认回退到 OpenAI 兼容模式
        logger.warning(f"[LLMFactory] 未知提供商 '{provider}'，尝试使用 OpenAI 兼容模式")
        return ChatOpenAI(api_key=api_key, base_url=api_base, **kwargs)
