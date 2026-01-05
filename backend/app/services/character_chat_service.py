from typing import List, Optional
from sqlmodel import Session, select
from app.db.models import ChatSession, ChatMessage, Card, LLMConfig
from app.services import llm_config_service
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

class CharacterChatService:
    def __init__(self, session: Session):
        self.session = session

    def create_session(self, project_id: int, character_card_id: int, title: str = "New Chat") -> ChatSession:
        chat_session = ChatSession(
            project_id=project_id,
            character_card_id=character_card_id,
            title=title
        )
        self.session.add(chat_session)
        self.session.commit()
        self.session.refresh(chat_session)
        return chat_session

    def get_session(self, session_id: int) -> Optional[ChatSession]:
        return self.session.get(ChatSession, session_id)
    
    def get_project_sessions(self, project_id: int) -> List[ChatSession]:
        statement = select(ChatSession).where(ChatSession.project_id == project_id).order_by(ChatSession.updated_at.desc())
        return self.session.exec(statement).all()

    def get_history(self, session_id: int) -> List[ChatMessage]:
        statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        return self.session.exec(statement).all()

    async def send_message(self, session_id: int, user_content: str, llm_config_id: Optional[int] = None) -> ChatMessage:
        # 1. Get Session and Character Card
        chat_session = self.get_session(session_id)
        if not chat_session:
            raise ValueError("Session not found")
        
        character_card = self.session.get(Card, chat_session.character_card_id)
        if not character_card:
            raise ValueError("Character card not found")

        # 2. Save User Message
        user_msg = ChatMessage(session_id=session_id, role="user", content=user_content)
        self.session.add(user_msg)
        self.session.commit()

        # 3. Initialize LLM
        llm_config = None
        if llm_config_id:
            llm_config = llm_config_service.get_llm_config(self.session, llm_config_id)
        
        if not llm_config:
             # Default to first available
             configs = llm_config_service.get_llm_configs(self.session)
             if not configs:
                 raise ValueError("No LLM config available")
             llm_config = configs[0]
        
        # Simple LLM init
        # Simple LLM init
        from app.services.langchain_assistant import build_chat_model
        llm = build_chat_model(
            session=self.session,
            llm_config_id=llm_config.id,
            temperature=0.7
        )

        # 4. Construct Prompt
        # Extract character info from card content
        char_info = character_card.content # Assuming content is a dict or string
        system_prompt = f"You are roleplaying as {character_card.title}. \n"
        if isinstance(char_info, dict):
            # Try to find relevant fields
            desc = char_info.get('content', '') or char_info.get('description', '')
            system_prompt += f"Character Description: {desc}\n"
            # Add other fields if available
            for key in ['personality', 'background', 'appearance']:
                if val := char_info.get(key):
                    system_prompt += f"{key.capitalize()}: {val}\n"
        else:
             system_prompt += f"Character Description: {char_info}\n"
        
        system_prompt += "Stay in character. Respond naturally. Do not break the fourth wall unless asked."

        history = self.get_history(session_id)
        messages = [SystemMessage(content=system_prompt)]
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # 5. Generate Response
        response = await llm.ainvoke(messages)
        ai_content = str(response.content)

        # 6. Save Assistant Message
        ai_msg = ChatMessage(session_id=session_id, role="assistant", content=ai_content)
        self.session.add(ai_msg)
        
        # Update session updated_at
        chat_session.updated_at = ai_msg.created_at
        self.session.add(chat_session)
        
        self.session.commit()
        self.session.refresh(ai_msg)

        return ai_msg
