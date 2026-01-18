from app.core.config import settings


from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, select
import shutil
import logging

logger = logging.getLogger(__name__)

from app.api.router import api_router
from app.db.session import engine
from app.db import models
from app.bootstrap.init_app import init_prompts, create_default_card_types
# 知识库初始化
from app.bootstrap.init_app import init_knowledge
from app.bootstrap.init_app import init_reserved_project
from app.bootstrap.init_app import init_workflows
from app.bootstrap.init_app import init_card_templates

def init_db():
    models.SQLModel.metadata.create_all(engine)

# 创建所有表
# models.Base.metadata.create_all(bind=engine)

from contextlib import asynccontextmanager

# 使用 lifespan 事件处理器替代 on_event
@asynccontextmanager
async def lifespan(app):
    # 启动时执行
    # 确保所有表存在（开发阶段可用；生产建议通过 Alembic 迁移）
    models.SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        init_prompts(session)
        create_default_card_types(session)
        # 初始化知识库
        init_knowledge(session)
        # 初始化保留项目
        init_reserved_project(session)
        # 初始化内置工作流
        init_workflows(session)
        # 初始化卡片模板
        init_card_templates(session)
        
        # 清理僵死工作流 (Zombie Workflow Cleanup)
        from app.db.models import WorkflowRun
        zombies = session.exec(select(WorkflowRun).where(WorkflowRun.status == "running")).all()
        if zombies:
            for z in zombies:
                z.status = "failed"
                z.error_json = {"error": "System restarted while running"}
            session.commit()
            logger.info(f"Cleaned up {len(zombies)} zombie workflows.")
    yield
    # 关闭时可添加清理逻辑（如有需要）

# 创建 FastAPI 应用实例，注册 lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 设置CORS中间件，允许所有来源的请求
# 这在开发环境中很方便，但在生产环境中应该更严格
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
    expose_headers=["X-Workflows-Started"],  # 允许浏览器读取此自定义响应头
)

# 包含API路由
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Welcome to NovelCreationEditor API"}


@app.get("/api/system/backup")
def backup_database():
    """Download the current database file."""
    db_path = settings.db_file
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(path=db_path, filename="aiauthor.db", media_type='application/x-sqlite3')


@app.post("/api/system/restore")
async def restore_database(file: UploadFile = File(...)):
    """Restore database from uploaded file. Overwrites existing database."""
    db_path = settings.db_file
    # Backup current db before overwrite (safety)
    backup_path = db_path.with_suffix(".bak")
    if db_path.exists():
        shutil.copy(db_path, backup_path)
    
    try:
        with open(db_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        # Restore from backup if failed
        if backup_path.exists():
            shutil.copy(backup_path, db_path)
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")
    
    return {"message": "Database restored successfully. Please restart the application."}

if __name__ == "__main__":
    import uvicorn
    # 添加reload=True，这样当代码修改时会自动重新加载
    # 配置更短的优雅关闭时间，便于 Ctrl+C 快速退出
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        timeout_graceful_shutdown=1,
    )

