import os
import re
from pathlib import Path
from typing import List, Dict

class DocumentStore:
    def __init__(self, docs_path: str):
        self.docs_path = Path(docs_path)
        self.documents: List[Dict[str, str]] = []
        self._load_documents()

    def _load_documents(self):
        if not self.docs_path.exists():
            return

        for file_path in self.docs_path.glob("**/*"):
            if file_path.suffix.lower() in [".md", ".txt"]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        self.documents.append({
                            "name": file_path.name,
                            "content": content
                        })
                except Exception as e:
                    print(f"Erro ao carregar {file_path}: {e}")
            elif file_path.suffix.lower() == ".pdf":
                try:
                    import pypdf
                    with open(file_path, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        content = ""
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                content += text + "\n"
                        
                        if content.strip():
                            self.documents.append({
                                "name": file_path.name,
                                "content": content
                            })
                except Exception as e:
                    print(f"Erro ao processar PDF {file_path}: {e}")

    def search(self, query: str, limit: int = 3) -> str:
        if not self.documents:
            return "Nenhum documento disponível na biblioteca."

        query_terms = re.findall(r'\w+', query.lower())
        results = []

        for doc in self.documents:
            content = doc["content"]
            score = sum(1 for term in query_terms if term in content.lower())
            if score > 0:
                results.append((score, doc["name"], content))

        results.sort(key=lambda x: x[0], reverse=True)

        if not results:
            return "Não encontrei informações específicas nos manuais sobre esse tema."

        output = "Informações encontradas nos documentos não estruturados:\n\n"
        for _, name, content in results[:limit]:
            output += f"--- Documento: {name} ---\n{content}\n\n"
        
        return output

DOC_STORE = DocumentStore(os.path.join(os.path.dirname(__file__), "..", "data", "documents"))
