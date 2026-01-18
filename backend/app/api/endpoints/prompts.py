from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session
from app.db.session import get_session
from app.schemas.prompt import PromptRead, PromptCreate, PromptUpdate
from app.schemas.response import ApiResponse
from app.services import prompt_service

router = APIRouter()

@router.post("/", response_model=ApiResponse[PromptRead], summary="创建新提示词")
def create_prompt(
    *,
    session: Session = Depends(get_session),
    prompt: PromptCreate,
):
    """
    Create a new prompt template.
    """
    new_prompt = prompt_service.create_prompt(session=session, prompt_create=prompt)
    return ApiResponse(data=new_prompt)

@router.get("/", response_model=ApiResponse[List[PromptRead]], summary="获取提示词列表")
def read_prompts(
    *,
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
):
    """
    Get a list of all prompt templates.
    """
    prompts = prompt_service.get_prompts(session=session, skip=skip, limit=limit)
    return ApiResponse(data=prompts)

@router.get("/{prompt_id}", response_model=ApiResponse[PromptRead], summary="获取单个提示词")
def read_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
):
    """
    Get details of a single prompt template by ID.
    """
    db_prompt = prompt_service.get_prompt(session=session, prompt_id=prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail="提示词未找到")
    return ApiResponse(data=db_prompt)

@router.put("/{prompt_id}", response_model=ApiResponse[PromptRead], summary="更新提示词")
def update_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
    prompt: PromptUpdate,
):
    """
    Update an existing prompt template.
    """
    updated_prompt = prompt_service.update_prompt(session=session, prompt_id=prompt_id, prompt_update=prompt)
    if not updated_prompt:
        raise HTTPException(status_code=404, detail="提示词未找到")
    return ApiResponse(data=updated_prompt)

@router.delete("/{prompt_id}", response_model=ApiResponse, summary="删除提示词")
def delete_prompt(
    *,
    session: Session = Depends(get_session),
    prompt_id: int,
):
    """
    Delete a prompt template.
    """
    db_prompt = prompt_service.get_prompt(session=session, prompt_id=prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail="提示词未找到")
    if getattr(db_prompt, 'built_in', False):
        raise HTTPException(status_code=400, detail="系统内置提示词不可删除")
    if not prompt_service.delete_prompt(session=session, prompt_id=prompt_id):
        raise HTTPException(status_code=404, detail="提示词未找到")
    return ApiResponse(message="提示词删除成功")

from pydantic import BaseModel

class PromptTestRequest(BaseModel):
    llm_config_id: int
    system_prompt: str
    user_prompt: str

@router.post("/test", response_model=ApiResponse, summary="测试提示词")
async def test_prompt(
    *,
    session: Session = Depends(get_session),
    body: PromptTestRequest,
):
    """
    Test a prompt with the specified LLM configuration.
    """
    from app.services.llm_factory import LLMFactory
    from app.services import llm_config_service
    from langchain_core.messages import SystemMessage, HumanMessage

    config = llm_config_service.get_llm_config(session=session, config_id=body.llm_config_id)
    if not config:
        raise HTTPException(status_code=404, detail="LLM 配置未找到")

    try:
        llm = LLMFactory.build_chat_model(
            provider=config.provider,
            model_name=config.model_name,
            api_key=config.api_key,
            api_base=config.api_base,
            temperature=0.7,
        )
        
        messages = [
            SystemMessage(content=body.system_prompt),
            HumanMessage(content=body.user_prompt)
        ]
        
        response = await llm.ainvoke(messages)
        return ApiResponse(data={"result": response.content})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"测试失败: {str(e)}")