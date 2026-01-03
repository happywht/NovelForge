from __future__ import annotations
import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from loguru import logger

# 默认存储路径
VECTOR_DB_PATH = os.path.join(os.getcwd(), "data", "vector_store")

class VectorService:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorService, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        if not os.path.exists(VECTOR_DB_PATH):
            os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB at {VECTOR_DB_PATH}")
        try:
            self._client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._client = None

    def get_collection(self, project_id: int):
        if not self._client:
            return None
        collection_name = f"project_{project_id}"
        return self._client.get_or_create_collection(name=collection_name)

    def add_texts(self, project_id: int, texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """
        添加文本到向量库
        """
        if not self._client:
            return False
        
        try:
            collection = self.get_collection(project_id)
            collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            logger.error(f"Vector add failed: {e}")
            return False

    def search(self, project_id: int, query: str, top_k: int = 5, filter: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        语义检索
        """
        if not self._client:
            return []
        
        try:
            collection = self.get_collection(project_id)
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter
            )
            
            # 格式化结果
            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i] if results['metadatas'] else {}
                    formatted_results.append({
                        "text": doc,
                        "metadata": meta,
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def delete_project_data(self, project_id: int):
        if not self._client:
            return
        try:
            collection_name = f"project_{project_id}"
            self._client.delete_collection(collection_name)
        except Exception as e:
            logger.warning(f"Failed to delete collection for project {project_id}: {e}")
