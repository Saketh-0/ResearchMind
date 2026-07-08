from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import os
import shutil
from collections import defaultdict

from utils.helpers import validate_api_key, get_api_key
from rag.loader import process_uploaded_files
from rag.embedder import create_vector_store, get_embedding_model
from langchain_community.vectorstores import FAISS
from rag.retriever import retrieve_relevant_chunks, format_context, get_source_references, get_confidence_level
from rag.chain import get_llm, get_rag_chain, query_rag_stream, query_rag
from api.database import init_db, append_message, get_chat_history, get_all_sessions, toggle_session_pin, toggle_session_archive, delete_session, register_user, get_user_by_email, update_user_password, merge_guest_data
import bcrypt

app = FastAPI(title="ResearchMind API")

@app.on_event("startup")
async def startup_event():
    await init_db()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Multi-user State Management
USER_STATES = defaultdict(lambda: {
    "vector_store": None,
    "chunks": [],
    "doc_names": [],
    "doc_heading": None,
    "loaded_session": None # Tracks which session is currently active in memory
})

VECTORSTORE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vectorstores")
os.makedirs(VECTORSTORE_BASE_DIR, exist_ok=True)

def ensure_session_loaded(user_id: str, session_id: str):
    """Loads the vector store from disk if not in memory."""
    state = USER_STATES[user_id]
    if state["loaded_session"] == session_id and state["vector_store"] is not None:
        return True # Already loaded
        
    session_dir = os.path.join(VECTORSTORE_BASE_DIR, user_id, session_id)
    if os.path.exists(session_dir):
        # Load FAISS
        state["vector_store"] = FAISS.load_local(session_dir, get_embedding_model(), allow_dangerous_deserialization=True)
        # Load meta
        meta_path = os.path.join(session_dir, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                state["doc_names"] = meta.get("doc_names", [])
                state["doc_heading"] = meta.get("doc_heading")
        else:
            state["doc_names"] = []
            state["doc_heading"] = None
            
        state["loaded_session"] = session_id
        return True
    return False

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    query: str
    history: List[ChatMessage]
    doc_heading: Optional[str] = None

class EvalRequest(BaseModel):
    session_id: str
    questions: List[str]
    ground_truths: List[str]


class AuthRequest(BaseModel):
    email: str
    password: str

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

class MockFile:
    def __init__(self, name, content):
        self.name = name
        self.content = content
    def read(self):
        return self.content

@app.post("/api/upload")
async def upload_documents(
    session_id: str = Form(...), 
    files: List[UploadFile] = File(...), 
    x_user_id: str = Header("anonymous")
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    # Check if a vector store already exists; if not, initialize chunks list
    if USER_STATES[x_user_id]["loaded_session"] != session_id:
        # Try to load existing
        if not ensure_session_loaded(x_user_id, session_id):
            USER_STATES[x_user_id]["vector_store"] = None
            USER_STATES[x_user_id]["chunks"] = []
            USER_STATES[x_user_id]["doc_names"] = []
            USER_STATES[x_user_id]["doc_heading"] = None
            USER_STATES[x_user_id]["loaded_session"] = session_id
    
    mock_files = []
    for f in files:
        content = await f.read()
        mock_files.append(MockFile(f.filename, content))

    chunks, total_pages, warnings = process_uploaded_files(mock_files)
    
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found in documents")
        
    vector_store = create_vector_store(chunks)
    
    # Store in user-specific state
    USER_STATES[x_user_id]["chunks"] = chunks
    USER_STATES[x_user_id]["doc_names"] = [f.name for f in mock_files]
    
    doc_heading = "Uploaded Document"
    if chunks:
        # Simple heuristic to extract a document heading
        doc_heading = chunks[0].page_content[:40].replace('\n', ' ').strip() + "..."
        
    # Merge with existing vector store if it exists
    existing_store = USER_STATES[x_user_id].get("vector_store")
    if existing_store:
        existing_store.merge_from(vector_store)
        vector_store = existing_store
        USER_STATES[x_user_id]["doc_names"].extend([f.name for f in mock_files])
        # Deduplicate
        USER_STATES[x_user_id]["doc_names"] = list(set(USER_STATES[x_user_id]["doc_names"]))
    else:
        USER_STATES[x_user_id]["doc_names"] = [f.name for f in mock_files]
        USER_STATES[x_user_id]["doc_heading"] = doc_heading
    
    USER_STATES[x_user_id]["vector_store"] = vector_store
    USER_STATES[x_user_id]["loaded_session"] = session_id
    
    # --- SAVE TO DISK ---
    session_dir = os.path.join(VECTORSTORE_BASE_DIR, x_user_id, session_id)
    os.makedirs(session_dir, exist_ok=True)
    vector_store.save_local(session_dir)
    
    # Save meta
    meta_path = os.path.join(session_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump({
            "doc_names": USER_STATES[x_user_id]["doc_names"],
            "doc_heading": USER_STATES[x_user_id]["doc_heading"]
        }, f)
    # --------------------
    
    return {
        "message": "Files processed successfully",
        "total_documents": len(mock_files),
        "total_chunks": len(chunks),
        "total_pages": total_pages,
        "warnings": warnings,
        "doc_names": USER_STATES[x_user_id]["doc_names"],
        "doc_heading": USER_STATES[x_user_id]["doc_heading"]
    }

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, x_user_id: str = Header("anonymous")):
    ensure_session_loaded(x_user_id, req.session_id)
    if not USER_STATES[x_user_id]["vector_store"]:
        raise HTTPException(status_code=400, detail="No documents uploaded. Please upload a PDF first.")
        
    api_key = get_api_key()
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="GROQ_API_KEY missing or invalid")
        
    llm = get_llm(api_key)
    rag_chain = get_rag_chain(llm)
    
    chunks_with_scores = retrieve_relevant_chunks(USER_STATES[x_user_id]["vector_store"], req.query)
    context = format_context(chunks_with_scores)
    sources = get_source_references(chunks_with_scores)
    confidence = get_confidence_level(chunks_with_scores)
    
    role_mapping = {"user": "human", "assistant": "ai"}
    chat_history = [(role_mapping.get(msg.role, msg.role), msg.content) for msg in req.history]
    
    # Save user query to DB immediately, with doc_heading in metadata if provided
    await append_message(x_user_id, req.session_id, "user", req.query, {"doc_heading": req.doc_heading} if req.doc_heading else None)
    
    async def generate():
        # Yield metadata first so UI can show sources immediately
        metadata = {
            "type": "metadata",
            "sources": sources,
            "confidence_level": confidence[0],
            "confidence_emoji": confidence[1]
        }
        yield f"data: {json.dumps(metadata)}\n\n"
        
        try:
            stream_gen = query_rag_stream(rag_chain, req.query, context, sources, confidence, chat_history)
            full_ai_response = ""
            for chunk in stream_gen:
                full_ai_response += chunk
                payload = {"type": "chunk", "content": chunk}
                yield f"data: {json.dumps(payload)}\n\n"
                # Give control back to event loop
                await asyncio.sleep(0.01)
                
            yield "data: [DONE]\n\n"
            # Save final AI response to DB
            await append_message(x_user_id, req.session_id, "assistant", full_ai_response, metadata)
        except Exception as e:
            payload = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(payload)}\n\n"
            yield "data: [DONE]\n\n"
        
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/chat/history/{session_id}")
async def fetch_chat_history(session_id: str, x_user_id: str = Header("anonymous")):
    history = await get_chat_history(x_user_id, session_id)
    return {"history": history}

@app.get("/api/chat/sessions")
async def fetch_all_sessions(x_user_id: str = Header("anonymous")):
    sessions = await get_all_sessions(x_user_id)
    return {"sessions": sessions}

@app.post("/api/chat/sessions/{session_id}/pin")
async def api_pin_session(session_id: str, is_pinned: bool, x_user_id: str = Header("anonymous")):
    await toggle_session_pin(x_user_id, session_id, is_pinned)
    return {"status": "success"}

@app.post("/api/chat/sessions/{session_id}/archive")
async def api_archive_session(session_id: str, is_archived: bool, x_user_id: str = Header("anonymous")):
    await toggle_session_archive(x_user_id, session_id, is_archived)
    return {"status": "success"}

@app.delete("/api/chat/sessions/{session_id}")
async def api_delete_session(session_id: str, x_user_id: str = Header("anonymous")):
    await delete_session(x_user_id, session_id)
    
    # Delete from disk
    session_dir = os.path.join(VECTORSTORE_BASE_DIR, x_user_id, session_id)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
        
    # Clear memory if it's the active one
    if USER_STATES[x_user_id]["loaded_session"] == session_id:
        USER_STATES[x_user_id]["vector_store"] = None
        USER_STATES[x_user_id]["chunks"] = []
        USER_STATES[x_user_id]["doc_names"] = []
        USER_STATES[x_user_id]["doc_heading"] = None
        USER_STATES[x_user_id]["loaded_session"] = None
        
    return {"status": "success"}

@app.post("/api/evaluate")
async def evaluate_endpoint(req: EvalRequest, x_user_id: str = Header("anonymous")):
    ensure_session_loaded(x_user_id, req.session_id) # Need session_id in EvalRequest?
    if not USER_STATES[x_user_id]["vector_store"]:
        raise HTTPException(status_code=400, detail="No documents uploaded yet.")
        
    api_key = get_api_key()
    llm = get_llm(api_key)
    
    from evaluation.evaluator import run_evaluation
    
    answers = []
    all_contexts = []
    
    for q in req.questions:
        chunks_with_scores = retrieve_relevant_chunks(USER_STATES[x_user_id]["vector_store"], q)
        context = format_context(chunks_with_scores)
        sources = get_source_references(chunks_with_scores)
        confidence = get_confidence_level(chunks_with_scores)
        
        result = query_rag(chain=get_rag_chain(llm), query=q, context=context, sources=sources, confidence=confidence)
        answers.append(result["answer"])
        
        ctx_list = [doc.page_content for doc, _ in chunks_with_scores]
        all_contexts.append(ctx_list)
        
    results = run_evaluation(req.questions, req.ground_truths, answers, all_contexts, llm)
    return results

@app.get("/api/status")
async def status_endpoint(session_id: Optional[str] = None, x_user_id: str = Header("anonymous")):
    if session_id:
        ensure_session_loaded(x_user_id, session_id)
        
    return {
        "status": "online",
        "documents_loaded": len(USER_STATES[x_user_id]["doc_names"]) if USER_STATES[x_user_id]["vector_store"] else 0,
        "doc_names": USER_STATES[x_user_id]["doc_names"],
        "doc_heading": USER_STATES[x_user_id].get("doc_heading")
    }

@app.post("/api/reset")
async def reset_endpoint(x_user_id: str = Header("anonymous")):
    USER_STATES[x_user_id]["vector_store"] = None
    USER_STATES[x_user_id]["chunks"] = []
    USER_STATES[x_user_id]["doc_names"] = []
    USER_STATES[x_user_id]["doc_heading"] = None
    USER_STATES[x_user_id]["loaded_session"] = None
    return {"status": "reset"}

@app.post("/api/auth/register")
async def register(req: AuthRequest, x_user_id: str = Header("anonymous")):
    email = req.email.strip().lower()
    if not email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password required")
        
    password_bytes = req.password.encode('utf-8')
    # truncate to 72 bytes if needed to avoid bcrypt limits
    password_hash = bcrypt.hashpw(password_bytes[:72], bcrypt.gensalt()).decode('utf-8')
    
    # We use their current x_user_id as their permanent id, UNLESS it's missing
    permanent_id = x_user_id if x_user_id.startswith('usr_') else "usr_" + os.urandom(8).hex()
    
    success = await register_user(email, password_hash, permanent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    return {"message": "Registration successful", "user_id": permanent_id, "email": email}

@app.post("/api/auth/login")
async def login(req: AuthRequest, x_user_id: str = Header("anonymous")):
    email = req.email.strip().lower()
    user = await get_user_by_email(email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    password_bytes = req.password.encode('utf-8')
    # verify password
    if not bcrypt.checkpw(password_bytes[:72], user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    permanent_id = user["user_id"]
    
    # Merge data! If they had active chats as a guest, merge them into their permanent account.
    if x_user_id.startswith('usr_') and x_user_id != permanent_id:
        await merge_guest_data(x_user_id, permanent_id)
        
        # Merge vectorstores on disk
        guest_dir = os.path.join(VECTORSTORE_BASE_DIR, x_user_id)
        perm_dir = os.path.join(VECTORSTORE_BASE_DIR, permanent_id)
        if os.path.exists(guest_dir):
            os.makedirs(perm_dir, exist_ok=True)
            for item in os.listdir(guest_dir):
                s = os.path.join(guest_dir, item)
                d = os.path.join(perm_dir, item)
                if not os.path.exists(d): # Avoid overwriting existing sessions
                    shutil.move(s, d)
            shutil.rmtree(guest_dir, ignore_errors=True)
            
    return {"message": "Login successful", "user_id": permanent_id, "email": email}

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

@app.post("/api/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    email = req.email.strip().lower()
    if not email or not req.new_password:
        raise HTTPException(status_code=400, detail="Email and new password required")
    
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    
    password_bytes = req.new_password.encode('utf-8')
    new_hash = bcrypt.hashpw(password_bytes[:72], bcrypt.gensalt()).decode('utf-8')
    
    success = await update_user_password(email, new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    
    return {"message": "Password reset successful. You can now sign in with your new password."}

# Serve static files from the build directory if it exists
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from starlette.types import Scope

    class NoCacheStaticFiles(StaticFiles):
        def file_response(self, mount_path: str, stat_result, scope: Scope, status_code: int = 200) -> FileResponse:
            response = super().file_response(mount_path, stat_result, scope, status_code)
            # Disable caching so users always get the latest version
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    app.mount("/", NoCacheStaticFiles(directory=frontend_dist, html=True), name="static")

