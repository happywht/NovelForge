import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "NovelForge API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database Settings
    AIAUTHOR_DB_PATH: Optional[str] = None
    
    # AI Model Settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = "https://api.openai.com/v1"
    
    # Neo4j Settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j"
    
    # Project Settings
    RESERVED_PROJECT_ID: int = 1
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db_file(self) -> Path:
        if self.AIAUTHOR_DB_PATH:
            return Path(self.AIAUTHOR_DB_PATH)
        
        # Default logic from session.py
        import sys
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            # backend/app/core/config.py -> backend
            base_dir = Path(__file__).resolve().parents[2]
        return base_dir / 'aiauthor.db'

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_file.as_posix()}"

settings = Settings()
