import os
from typing import Dict, List

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import INGESTION_PROVIDER, LLAMAPARSE_API_KEY

_COLLECTION  = "helix_docs"
_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
_CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8093"))

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)

_embeddings = HuggingFaceEmbeddings(
    model_name=_EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

_chroma_client = chromadb.HttpClient(host=_CHROMA_HOST, port=_CHROMA_PORT)
_vectorstore   = Chroma(
    collection_name=_COLLECTION,
    embedding_function=_embeddings,
    client=_chroma_client,
    collection_metadata={"hnsw:space": "cosine"},
)


# ── Extraction helpers ─────────────────────────────────────────────────

def _extract_llamaparse(documents: List[Dict], ambito: str) -> List[Document]:
    if not LLAMAPARSE_API_KEY:
        raise ValueError(
            "LLAMAPARSE_API_KEY non impostato in .env. "
            "Imposta INGESTION_PROVIDER=langchain oppure fornisci la chiave LlamaIndex."
        )

    import nest_asyncio
    nest_asyncio.apply()

    from llama_parse import LlamaParse

    parser = LlamaParse(
        api_key=LLAMAPARSE_API_KEY,
        result_type="markdown",
        language="it",
        verbose=False,
    )

    lc_docs: List[Document] = []
    for doc in documents:
        print(f"[LlamaParse] Parsing {doc['filename']} (ambito: {ambito})...")
        try:
            llama_docs = parser.load_data(doc["filepath"])
            for ld in llama_docs:
                page_num = getattr(ld, "metadata", {}).get("page_label", 1)
                for chunk in _splitter.split_text(ld.text):
                    lc_docs.append(Document(
                        page_content=chunk,
                        metadata={"filename": doc["filename"], "page": page_num, "ambito": ambito},
                    ))
        except Exception as e:
            print(f"[LlamaParse] Errore su {doc['filename']}: {e}")

    return lc_docs


def _extract_langchain(documents: List[Dict], ambito: str) -> List[Document]:
    lc_docs: List[Document] = []
    for doc in documents:
        for page in doc["pages"]:
            for chunk in _splitter.split_text(page["text"]):
                lc_docs.append(Document(
                    page_content=chunk,
                    metadata={"filename": doc["filename"], "page": page["page"], "ambito": ambito},
                ))
    return lc_docs


# ── Public API ─────────────────────────────────────────────────────────

def build_index(documents: List[Dict], ambito: str) -> None:
    col = _chroma_client.get_or_create_collection(_COLLECTION)

    # Remove existing chunks for this ambito only
    existing = col.get(where={"ambito": ambito}, include=[])
    if existing["ids"]:
        col.delete(ids=existing["ids"])

    if not documents:
        print(f"[VectorStore] Nessun documento per l'ambito '{ambito}'.")
        return

    provider = INGESTION_PROVIDER.lower().strip()
    print(f"[VectorStore] Provider: {provider} — ambito: {ambito}")

    lc_docs = (
        _extract_llamaparse(documents, ambito)
        if provider == "llamaparse"
        else _extract_langchain(documents, ambito)
    )

    if not lc_docs:
        print(f"[VectorStore] Nessun chunk per l'ambito '{ambito}'.")
        return

    print(f"[VectorStore] Indicizzazione {len(lc_docs)} chunk per '{ambito}'...")
    _vectorstore.add_documents(lc_docs)
    print(f"[VectorStore] Completato per '{ambito}'.")


def search(query: str, ambito: str, n_results: int = 10) -> List[Dict]:
    col = _chroma_client.get_or_create_collection(_COLLECTION)
    if col.count() == 0:
        return []

    results = _vectorstore.similarity_search_with_score(
        query, k=n_results, filter={"ambito": ambito}
    )

    by_file: Dict[str, Dict] = {}
    for lc_doc, dist in results:
        fname = lc_doc.metadata.get("filename", "unknown")
        score = 1.0 - float(dist)
        if fname not in by_file:
            by_file[fname] = {"filename": fname, "score": score, "chunks": [lc_doc.page_content]}
        else:
            by_file[fname]["chunks"].append(lc_doc.page_content)
            by_file[fname]["score"] = max(by_file[fname]["score"], score)

    return [
        {
            "filename": info["filename"],
            "score":    info["score"],
            "excerpt":  "\n...\n".join(info["chunks"][:3]),
        }
        for info in sorted(by_file.values(), key=lambda x: -x["score"])
    ]
