from fastapi import APIRouter, HTTPException
from typing import Any, Dict

from app.services.kg_provider import get_provider
from app.schemas.response import ApiResponse

router = APIRouter()

@router.get("/project/{project_id}/graph", response_model=ApiResponse[Dict[str, Any]], summary="获取项目的知识图谱")
def get_project_graph(project_id: int, pov_character: str = None):
    try:
        provider = get_provider()
        if pov_character:
            # 如果提供了 POV 角色，则查询子图
            graph = provider.query_subgraph(project_id, pov_character=pov_character)
        else:
            graph = provider.get_full_graph(project_id)
        return ApiResponse(data=graph)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图谱失败: {str(e)}")
