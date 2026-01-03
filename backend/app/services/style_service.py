from typing import List, Dict
from app.services.vector_service import VectorService

class StyleService:
    def __init__(self):
        self.vector_svc = VectorService()

    def retrieve_relevant_styles(self, project_id: int, content_snippet: str, top_k: int = 3) -> List[str]:
        """
        根据当前内容片段，检索最相关的风格参考（高分文段）
        """
        # 构造查询：寻找与当前情节/描写相似的已写内容，作为风格参考
        # 这里假设向量库中存储了"chapter"类型的文本块
        results = self.vector_svc.search(
            project_id=project_id,
            query=content_snippet,
            top_k=top_k,
            filter={"type": "chapter"}  # 仅检索章节正文
        )
        
        styles = []
        for res in results:
            text = res.get("text", "").strip()
            if text:
                styles.append(text)
        
        return styles
