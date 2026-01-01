from fastapi import APIRouter, HTTPException
from typing import Any, Dict

from app.services.kg_provider import get_provider
from app.schemas.response import ApiResponse

router = APIRouter()

@router.get("/{project_id}", response_model=ApiResponse[Dict[str, Any]], summary="获取项目的完整知识图谱")
def get_project_graph(project_id: int):
    try:
        provider = get_provider()
        graph = provider.get_full_graph(project_id)
        return ApiResponse(data=graph)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图谱失败: {str(e)}")
