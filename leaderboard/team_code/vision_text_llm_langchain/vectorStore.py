import os
from langchain.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings # pip install -qU langchain-openai
from langchain_core.embeddings import FakeEmbeddings # pip install -qU langchain-core
from langchain_huggingface import HuggingFaceEmbeddings # pip install -qU langchain-huggingface
from langchain.docstore.document import Document

class DrivingMemory:
    def __init__(self, emb_type, rule_path='./Chroma/rule_db', emergency_path='./Chroma/memory_db') -> None:
        if emb_type == 'openai':
            self.embedding = OpenAIEmbeddings()
        elif emb_type == 'huggingface':
            self.embedding = HuggingFaceEmbeddings(model="sentence-transformers/all-mpnet-base-v2")
        else:
            self.embedding = FakeEmbeddings(size=4096)

        self.rules_memory = Chroma(
            collection_name="example_collection",
            embedding_function=self.embedding,
            persist_directory=rule_path,
        )
        print("==========Loaded ", rule_path, " Memory, Now the database has ",
              self.rules_memory._collection.count(), " rule items.==========")

        self.emergency_memory = Chroma(
            collection_name="example_collection",
            embedding_function=self.embedding,
            persist_directory=emergency_path,
        )
        print("==========Loaded ", emergency_path, " Memory, Now the database has ",
              self.emergency_memory._collection.count(), " emergency items.==========")

    def retriveMemory(self, query_scenario: str, top_k: int = 5):
        similarity_results = self.rules_memory.similarity_search_with_score(query_scenario, k=top_k)
        fewshot_results = []
        for idx in range(0, len(similarity_results)):
            # print(f"similarity score: {similarity_results[idx][1]}")
            fewshot_results.append(similarity_results[idx][0].metadata)
        return fewshot_results

    def addMemory(self, sce_descrip: str, analysis: str, action: int, waypoints: list, comments: str = ""):
        # 检查是否已存在相同内容
        existing = self.rules_memory.get(
            where_document={"$contains": sce_descrip},
            limit=1
        )

        if existing['ids']:
            # 已存在则更新
            self._updateMemory(existing['ids'][0], analysis, action, waypoints, comments)
        else:
            # 不存在则新增
            doc = Document(
                page_content=sce_descrip,
                metadata={
                    "analysis": analysis,
                    'waypoints': waypoints,
                    'action': action,
                    'comments': comments
                }
            )
            # 使用add_documents自动生成ID
            self.rules_memory.add_documents(documents=[doc])
            print(f"Added new memory item. Total items: {self.rules_memory._collection.count()}")

    def updateMemory(self, ids: str, analysis: str, action: int, waypoints: list, comments: str = ""):
        """公开的更新接口"""
        if isinstance(ids, str):
            ids = [ids]
        for doc_id in ids:
            self._updateMemory(doc_id, analysis, action, waypoints, comments)

    def _updateMemory(self, doc_id: str, analysis: str, action: int, waypoints: list, comments: str = ""):
        """内部使用的更新方法"""
        self.rules_memory._collection.update(
            ids=[doc_id],
            metadatas=[{
                "analysis": analysis,
                'waypoints': waypoints,
                'action': action,
                'comments': comments
            }]
        )
        print(f"Updated memory item {doc_id}. Total items: {self.rules_memory._collection.count()}")

    def deleteMemory(self, ids: str or list):
        """删除一个或多个项目"""
        if isinstance(ids, str):
            ids = [ids]
        self.rules_memory.delete(ids=ids)
        print(f"Deleted {len(ids)} items. Total items: {self.rules_memory._collection.count()}")

    def combineMemory(self, other_memory):
        other_documents = other_memory.scenario_memory._collection.get(
            include=['documents', 'metadatas', 'embeddings'])
        current_documents = self.rules_memory._collection.get(
            include=['documents', 'metadatas', 'embeddings'])
        for i in range(0, len(other_documents['embeddings'])):
            if other_documents['embeddings'][i] in current_documents['embeddings']:
                print("Already have one memory item, skip.")
            else:
                self.rules_memory._collection.add(
                    embeddings=other_documents['embeddings'][i],
                    metadatas=other_documents['metadatas'][i],
                    documents=other_documents['documents'][i],
                    ids=other_documents['ids'][i]
                )
        print("Merge complete. Now the database has ", self.rules_memory._collection.count(), " rule items.")