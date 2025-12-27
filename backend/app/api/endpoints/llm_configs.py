
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.db.session import get_session
from app.schemas.llm_config import LLMConfigCreate, LLMConfigRead, LLMConfigUpdate, LLMConnectionTest
from app.schemas.response import ApiResponse
from app.services import llm_config_service
from typing import List

router = APIRouter()

@router.post("/", response_model=ApiResponse[LLMConfigRead])
def create_llm_config_endpoint(config_in: LLMConfigCreate, session: Session = Depends(get_session)):
    if config_in.display_name is None or config_in.display_name == "":
        config_in.display_name = config_in.model_name
    config = llm_config_service.create_llm_config(session=session, config_in=config_in)
    return ApiResponse(data=config)

@router.get("/", response_model=ApiResponse[List[LLMConfigRead]])
def get_llm_configs_endpoint(session: Session = Depends(get_session)):
    configs = llm_config_service.get_llm_configs(session=session)
    return ApiResponse(data=configs)

@router.put("/{config_id}", response_model=ApiResponse[LLMConfigRead])
def update_llm_config_endpoint(config_id: int, config_in: LLMConfigUpdate, session: Session = Depends(get_session)):
    config = llm_config_service.update_llm_config(session=session, config_id=config_id, config_in=config_in)
    if not config:
        raise HTTPException(status_code=404, detail="LLM Config not found")
    return ApiResponse(data=config)

@router.delete("/{config_id}", response_model=ApiResponse)
def delete_llm_config_endpoint(config_id: int, session: Session = Depends(get_session)):
    success = llm_config_service.delete_llm_config(session=session, config_id=config_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM Config not found")
    return ApiResponse(message="LLM Config deleted successfully")

@router.post("/test", response_model=ApiResponse, summary="测试 LLM 连接")
async def test_llm_connection_endpoint(connection_data: LLMConnectionTest, session: Session = Depends(get_session)):
    """使用传入参数临时构造一个 LangChain ChatModel 并发起一次最小调用以验证连通性。"""
    try:
        provider = (connection_data.provider or "").lower()

        # 延迟导入以避免在未使用时增加启动开销
        if provider == "openai_compatible":
            from langchain_qwq import ChatQwen
            #原生的ChatOpenAI虽然能够支持OpenAI兼容的各种模型，但是似乎对推理模式支持不够好模式
            kwargs: dict = {
                "model": connection_data.model_name,
                "api_key": connection_data.api_key,
            }
            if connection_data.api_base:
                kwargs["base_url"] = connection_data.api_base
            model = ChatQwen(**kwargs)

        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": connection_data.model_name,
                "api_key": connection_data.api_key,
            }
            # Support custom base_url for OpenAI-compatible APIs
            if connection_data.api_base:
                kwargs["base_url"] = connection_data.api_base
            model = ChatOpenAI(**kwargs)

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            kwargs = {
                "model": connection_data.model_name,
                "api_key": connection_data.api_key,
            }
            model = ChatAnthropic(**kwargs)
        
        elif provider == "zhipu_anthropic":
            from langchain_anthropic import ChatAnthropic
            
            # Zhipu AI provides Anthropic-compatible API
            # Default base_url: https://open.bigmodel.cn/api/anthropic
            base_url = connection_data.api_base or "https://open.bigmodel.cn/api/anthropic"
            
            kwargs = {
                "model": connection_data.model_name,  # e.g., glm-4-flash, glm-4-plus
                "api_key": connection_data.api_key,
                "base_url": base_url,
            }
            model = ChatAnthropic(**kwargs)

        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            kwargs = {
                "model": connection_data.model_name,
                "api_key": connection_data.api_key,
            }
            model = ChatGoogleGenerativeAI(**kwargs)

        # Support for DeepSeek, Moonshot, and other OpenAI-compatible providers
        elif provider in ["deepseek", "moonshot", "qwen", "minimax", "zhipu", "baichuan"]:
            from langchain_openai import ChatOpenAI
            
            if not connection_data.api_base:
                raise HTTPException(status_code=400, detail=f"提供商 '{provider}' 需要指定 api_base 参数")
            
            kwargs = {
                "model": connection_data.model_name,
                "api_key": connection_data.api_key,
                "base_url": connection_data.api_base,
            }
            model = ChatOpenAI(**kwargs)

        else:
            raise HTTPException(status_code=400, detail=f"不支持的提供商类型: {connection_data.provider}。支持的类型: openai, openai_compatible, anthropic, zhipu_anthropic, google, deepseek, moonshot, qwen, minimax, zhipu, baichuan")

        # 发送一次最小请求以验证连通性
        await model.ainvoke("ping")
        return ApiResponse(message="Connection successful")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接测试失败: {str(e)}")


@router.post("/{config_id}/reset-usage", response_model=ApiResponse, summary="重置统计（输入/输出token与调用次数清零）")
def reset_llm_usage(config_id: int, session: Session = Depends(get_session)):
    ok = llm_config_service.reset_usage(session, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="LLM Config not found")
    return ApiResponse(message="Usage reset")