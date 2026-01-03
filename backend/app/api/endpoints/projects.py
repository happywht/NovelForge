from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.db import get_session
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.response import ApiResponse
from app.services import project_service
from app.services.reverse_architect_service import ReverseArchitectService
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter()

@router.post("/", response_model=ApiResponse[ProjectRead])
def create_project_endpoint(project_in: ProjectCreate, session: Session = Depends(get_session)):
    project = project_service.create_project(session=session, project_in=project_in)
    return ApiResponse(data=project)

@router.get("/", response_model=ApiResponse[List[ProjectRead]])
def get_projects_endpoint(session: Session = Depends(get_session)):
    projects = project_service.get_projects(session=session)
    return ApiResponse(data=projects)

@router.get("/free", response_model=ApiResponse[ProjectRead])
def get_free_project_endpoint(session: Session = Depends(get_session)):
    proj = project_service.get_or_create_free_project(session=session)
    return ApiResponse(data=proj)

@router.get("/{project_id}", response_model=ApiResponse[ProjectRead])
def get_project_endpoint(project_id: int, session: Session = Depends(get_session)):
    project = project_service.get_project(session=session, project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=project)

@router.put("/{project_id}", response_model=ApiResponse[ProjectRead])
def update_project_endpoint(project_id: int, project_in: ProjectUpdate, session: Session = Depends(get_session)):
    project = project_service.update_project(session=session, project_id=project_id, project_in=project_in)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(data=project)

@router.delete("/{project_id}", response_model=ApiResponse)
def delete_project_endpoint(project_id: int, session: Session = Depends(get_session)):
    success = project_service.delete_project(session=session, project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return ApiResponse(message="Project deleted successfully")

class ReverseImportRequest(BaseModel):
    text: str
    regex_pattern: Optional[str] = None

@router.post("/{project_id}/reverse-preview")
def reverse_preview_endpoint(project_id: int, payload: ReverseImportRequest, session: Session = Depends(get_session)):
    """
    预览小说正文切分结果
    """
    service = ReverseArchitectService(session)
    try:
        chapters = service.split_text(payload.text, payload.regex_pattern)
        return ApiResponse(data={"chapters": chapters}, message=f"成功识别 {len(chapters)} 个章节")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")

@router.post("/{project_id}/reverse-import")
def reverse_import_endpoint(project_id: int, payload: ReverseImportRequest, session: Session = Depends(get_session)):
    """
    批量导入小说正文，自动切分章节并创建卡片
    """
    service = ReverseArchitectService(session)
    try:
        created_ids = service.batch_import_chapters(project_id, payload.text, payload.regex_pattern)
        return ApiResponse(data={"created_card_ids": created_ids}, message=f"成功导入 {len(created_ids)} 个章节")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")