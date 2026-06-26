import os
import re
from pathlib import Path
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions

class DocumentStore:
    def __init__(self, docs_path: str, persist_path: str = "data/chroma"):
        self.docs_path = Path(docs_path)
        self.persist_path = Path(persist_path)
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="sismo_library",
            embedding_function=self.embedding_fn
        )
        
        # Only load if collection is empty
        if self.collection.count() == 0:
            self._load_and_index_documents()

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        chunks = []
        if not text:
            return chunks
            
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def _load_and_index_documents(self):
        if not self.docs_path.exists():
            return

        documents_to_upsert = []
        metadatas = []
        ids = []

        for file_path in self.docs_path.glob("**/*"):
            content = ""
            if file_path.suffix.lower() in [".md", ".txt"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    print(f"Erro ao carregar {file_path}: {e}")
            elif file_path.suffix.lower() == ".pdf":
                try:
                    import pypdf
                    with open(file_path, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                content += text + "\n"
                except Exception as e:
                    print(f"Erro ao processar PDF {file_path}: {e}")

            if content.strip():
                chunks = self._chunk_text(content.strip())
                for i, chunk in enumerate(chunks):
                    documents_to_upsert.append(chunk)
                    metadatas.append({"source": file_path.name, "chunk": i})
                    ids.append(f"{file_path.name}_{i}")

        if documents_to_upsert:
            self.collection.upsert(
                documents=documents_to_upsert,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Indexados {len(documents_to_upsert)} segmentos de {len(set(m['source'] for m in metadatas))} documentos.")

    def search(self, query: str, limit: int = 5) -> dict:
        if self.collection.count() == 0:
            return {"error": "Nenhum documento disponível na biblioteca vetorial.", "results": []}

        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return {"error": "Não encontrei informações relevantes na biblioteca.", "results": []}

        formatted_results = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        
        for doc, meta in zip(docs, metas):
            formatted_results.append({
                "source": meta.get("source", "desconhecido"),
                "content": doc
            })
        
        return {
            "results_count": len(formatted_results),
            "results": formatted_results
        }

# Path logic adjustment for Docker/Local consistency
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "documents"
CHROMA_DIR = BASE_DIR / "data" / "chroma"

DOC_STORE = DocumentStore(str(DOCS_DIR), str(CHROMA_DIR))
