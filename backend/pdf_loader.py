import os
from typing import List, Dict
import fitz  # PyMuPDF


def load_pdfs(docs_folder: str) -> List[Dict]:
    """Extract text from all PDFs in the given folder."""
    documents = []

    if not os.path.exists(docs_folder):
        return documents

    for filename in sorted(os.listdir(docs_folder)):
        if not filename.lower().endswith(".pdf"):
            continue
        filepath = os.path.join(docs_folder, filename)
        try:
            doc = fitz.open(filepath)
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append({"page": page_num + 1, "text": text.strip()})
            full_text = "\n".join(p["text"] for p in pages)
            documents.append({
                "filename": filename,
                "filepath": filepath,
                "pages": pages,
                "full_text": full_text,
            })
            doc.close()
            print(f"Loaded: {filename} ({len(pages)} pages)")
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    return documents
