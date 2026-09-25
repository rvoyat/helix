import json
import os
import re
import shutil
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

import backend.auth as auth_module
import backend.llm_settings as llm_settings
from backend.config import DOCS_FOLDER
from backend.pdf_loader import load_pdfs
from backend.vector_store import build_index, _chroma_client, _COLLECTION
from agents.orchestrator import Orchestrator

AMBITI_FILE = "./ambiti.json"

orchestrator: Optional[Orchestrator] = None
_ambiti: List[Dict] = []


# ── Ambiti config helpers ──────────────────────────────────────────────

def _load_ambiti_config() -> List[Dict]:
    if os.path.exists(AMBITI_FILE):
        with open(AMBITI_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_ambiti_config(ambiti: List[Dict]) -> None:
    with open(AMBITI_FILE, "w", encoding="utf-8") as f:
        json.dump(ambiti, f, ensure_ascii=False, indent=2)


def _ambito_folder(slug: str) -> str:
    return os.path.join(DOCS_FOLDER, slug)


def _doc_info(doc: dict) -> dict:
    size = os.path.getsize(doc["filepath"]) if os.path.exists(doc["filepath"]) else 0
    return {"filename": doc["filename"], "pages": len(doc["pages"]), "size": size}


def _reload_ambito(slug: str) -> List[dict]:
    folder = _ambito_folder(slug)
    os.makedirs(folder, exist_ok=True)
    docs = load_pdfs(folder)
    build_index(docs, slug)
    return docs


# ── Startup ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, _ambiti
    os.makedirs(DOCS_FOLDER, exist_ok=True)
    _ambiti = _load_ambiti_config()

    for ambito in _ambiti:
        slug = ambito["slug"]
        print(f"[Startup] Caricamento documenti per ambito '{slug}'...")
        folder = _ambito_folder(slug)
        os.makedirs(folder, exist_ok=True)
        docs = load_pdfs(folder)
        build_index(docs, slug)
        print(f"[Startup] '{slug}': {len(docs)} documento/i indicizzato/i.")

    orchestrator = Orchestrator()
    yield


# ── Auth middleware ────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    _PUBLIC = {"/auth/login", "/health"}

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in self._PUBLIC or request.url.path.startswith("/docs/file"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Non autenticato."}, status_code=401)
        user = auth_module.get_user(auth[7:])
        if not user:
            return JSONResponse({"detail": "Sessione scaduta o non valida."}, status_code=401)
        request.state.user = user
        return await call_next(request)


app = FastAPI(title="HELIX API", version="1.0.0", lifespan=lifespan)

# AuthMiddleware added first (innermost), CORSMiddleware added second (outermost — runs first)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── FastAPI dependencies ───────────────────────────────────────────────

async def require_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or user["role"] != "admin":
        raise HTTPException(403, "Accesso riservato agli amministratori.")
    return user


# ── Pydantic models ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    ambito: str


class AmbitoCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    color: str = "#A100FF"
    icon: str = "📂"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "guest"


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    default_ambito: Optional[str] = None


class MeUpdate(BaseModel):
    password: Optional[str] = None
    default_ambito: Optional[str] = None
    theme: Optional[str] = None


class LLMSettings(BaseModel):
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-5"
    INGESTION_PROVIDER: str = "langchain"
    LLAMAPARSE_API_KEY: str = ""


# ── Health check (public) ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Auth endpoints ─────────────────────────────────────────────────────

@app.post("/auth/login")
async def login(req: LoginRequest):
    token = auth_module.login(req.username, req.password)
    if not token:
        raise HTTPException(401, "Credenziali non valide.")
    user = auth_module.get_user(token)
    return {"token": token, "user": user}


@app.post("/auth/logout")
async def logout(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        auth_module.logout(auth[7:])
    return {"message": "Logout effettuato."}


@app.get("/auth/me")
async def me(request: Request):
    return request.state.user


@app.put("/auth/me")
async def update_me(req: MeUpdate, request: Request):
    username = request.state.user["username"]
    auth_module.update_user(username, password=req.password, default_ambito=req.default_ambito, theme=req.theme)
    token = request.headers.get("Authorization", "")[7:]
    return auth_module.get_user(token)


# ── Admin endpoints ────────────────────────────────────────────────────

@app.get("/admin/users")
async def admin_list_users(_: dict = Depends(require_admin)):
    return {"users": auth_module.list_users()}


@app.post("/admin/users")
async def admin_create_user(req: UserCreate, _: dict = Depends(require_admin)):
    if not auth_module.create_user(req.username, req.password, req.role):
        raise HTTPException(409, f"Utente '{req.username}' già esistente.")
    return {"message": f"Utente '{req.username}' creato."}


@app.put("/admin/users/{username}")
async def admin_update_user(username: str, req: UserUpdate, _: dict = Depends(require_admin)):
    if not auth_module.update_user(
        username, password=req.password, role=req.role, default_ambito=req.default_ambito
    ):
        raise HTTPException(404, f"Utente '{username}' non trovato.")
    return {"message": f"Utente '{username}' aggiornato."}


@app.delete("/admin/users/{username}")
async def admin_delete_user(username: str, request: Request, _: dict = Depends(require_admin)):
    if username == request.state.user["username"]:
        raise HTTPException(400, "Non puoi eliminare te stesso.")
    if not auth_module.delete_user(username):
        raise HTTPException(404, f"Utente '{username}' non trovato.")
    return {"message": f"Utente '{username}' eliminato."}


@app.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(require_admin)):
    return llm_settings.load()


@app.put("/admin/settings")
async def admin_update_settings(req: LLMSettings, _: dict = Depends(require_admin)):
    llm_settings.save(req.model_dump())
    return {"message": "Impostazioni LLM aggiornate."}


# ── Ambiti management endpoints ────────────────────────────────────────

@app.get("/ambiti")
async def list_ambiti():
    return {"ambiti": _ambiti}


@app.post("/ambiti")
async def create_ambito(req: AmbitoCreate, _: dict = Depends(require_admin)):
    global _ambiti
    if any(a["slug"] == req.slug for a in _ambiti):
        raise HTTPException(status_code=409, detail=f"Ambito '{req.slug}' già esistente.")
    if not re.match(r'^[a-z0-9-]+$', req.slug):
        raise HTTPException(
            status_code=400,
            detail="Lo slug deve contenere solo lettere minuscole, numeri e trattini.",
        )

    new_ambito = {
        "slug": req.slug,
        "name": req.name,
        "description": req.description,
        "color": req.color,
        "icon": req.icon,
    }
    _ambiti.append(new_ambito)
    _save_ambiti_config(_ambiti)
    os.makedirs(_ambito_folder(req.slug), exist_ok=True)

    return {"message": f"Ambito '{req.name}' creato con successo.", "ambito": new_ambito}


@app.delete("/ambiti/{slug}")
async def delete_ambito(slug: str, _: dict = Depends(require_admin)):
    global _ambiti
    ambito = next((a for a in _ambiti if a["slug"] == slug), None)
    if not ambito:
        raise HTTPException(status_code=404, detail=f"Ambito '{slug}' non trovato.")

    col = _chroma_client.get_or_create_collection(_COLLECTION)
    existing = col.get(where={"ambito": slug}, include=[])
    if existing["ids"]:
        col.delete(ids=existing["ids"])

    folder = _ambito_folder(slug)
    if os.path.exists(folder):
        shutil.rmtree(folder)

    _ambiti = [a for a in _ambiti if a["slug"] != slug]
    _save_ambiti_config(_ambiti)

    return {"message": f"Ambito '{ambito['name']}' eliminato con successo."}


# ── Chat endpoint ─────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    if not any(a["slug"] == req.ambito for a in _ambiti):
        raise HTTPException(status_code=400, detail=f"Ambito '{req.ambito}' non trovato.")
    return orchestrator.process(req.message, req.session_id, req.ambito)


# ── Document management endpoints ─────────────────────────────────────

@app.get("/docs-list")
async def docs_list(ambito: str = Query(...)):
    if not any(a["slug"] == ambito for a in _ambiti):
        raise HTTPException(status_code=400, detail=f"Ambito '{ambito}' non trovato.")
    docs = load_pdfs(_ambito_folder(ambito))
    return {"documents": [_doc_info(d) for d in docs]}


@app.get("/docs/file")
async def get_doc_file(filename: str = Query(...), ambito: str = Query(...)):
    folder_abs = os.path.abspath(_ambito_folder(ambito))
    filepath   = os.path.abspath(os.path.join(folder_abs, filename))
    if not filepath.startswith(folder_abs + os.sep) and filepath != folder_abs:
        raise HTTPException(status_code=400, detail="Percorso non valido.")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File non trovato.")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)


@app.post("/docs/upload")
async def upload_doc(ambito: str = Query(...), file: UploadFile = File(...)):
    if not any(a["slug"] == ambito for a in _ambiti):
        raise HTTPException(status_code=400, detail=f"Ambito '{ambito}' non trovato.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo file PDF sono supportati.")
    folder = _ambito_folder(ambito)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, file.filename), "wb") as f:
        shutil.copyfileobj(file.file, f)
    docs = _reload_ambito(ambito)
    return {
        "message": f"'{file.filename}' caricato con successo.",
        "documents": [_doc_info(d) for d in docs],
    }


@app.put("/docs/{filename}")
async def replace_doc(filename: str, ambito: str = Query(...), file: UploadFile = File(...)):
    if not any(a["slug"] == ambito for a in _ambiti):
        raise HTTPException(status_code=400, detail=f"Ambito '{ambito}' non trovato.")
    dest = os.path.join(_ambito_folder(ambito), filename)
    if not os.path.exists(dest):
        raise HTTPException(status_code=404, detail="File non trovato.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo file PDF sono supportati.")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    docs = _reload_ambito(ambito)
    return {
        "message": f"'{filename}' aggiornato con successo.",
        "documents": [_doc_info(d) for d in docs],
    }


@app.delete("/docs/{filename}")
async def delete_doc(filename: str, ambito: str = Query(...)):
    if not any(a["slug"] == ambito for a in _ambiti):
        raise HTTPException(status_code=400, detail=f"Ambito '{ambito}' non trovato.")
    filepath = os.path.join(_ambito_folder(ambito), filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File non trovato.")
    os.remove(filepath)
    docs = _reload_ambito(ambito)
    return {
        "message": f"'{filename}' eliminato con successo.",
        "documents": [_doc_info(d) for d in docs],
    }


@app.post("/docs/reindex")
async def reindex_docs(ambito: str = Query(None)):
    if ambito:
        if not any(a["slug"] == ambito for a in _ambiti):
            raise HTTPException(status_code=400, detail=f"Ambito '{ambito}' non trovato.")
        docs = _reload_ambito(ambito)
        return {
            "message": f"Reindicizzazione completata: {len(docs)} documento/i per '{ambito}'.",
            "documents": [_doc_info(d) for d in docs],
        }

    total = 0
    for a in _ambiti:
        docs = _reload_ambito(a["slug"])
        total += len(docs)
    return {"message": f"Reindicizzazione globale completata: {total} documento/i totali."}
