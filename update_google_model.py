import sys
import os
from sqlmodel import Session, select

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.session import engine
from app.db.models import LLMConfig

def update_model():
    with Session(engine) as session:
        config = session.exec(select(LLMConfig).where(LLMConfig.provider == "google")).first()
        if config:
            print(f"Updating config for: {config.display_name}")
            config.model_name = "gemini-2.5-pro"
            config.display_name = "Google Gemini 2.5 Pro"
            session.add(config)
            session.commit()
            session.refresh(config)
            print(f"Updated to model: {config.model_name}")
        else:
            print("Config not found.")

if __name__ == "__main__":
    update_model()
