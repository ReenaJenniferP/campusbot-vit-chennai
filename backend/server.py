# server.py
# Simple RAG server:
# - embeds the user question with Ollama (mxbai-embed-large)
# - retrieves from FAISS (vit_faiss.index + vit_meta.jsonl)
# - filters boilerplate/navigation chunks
# - adaptively increases K if results look weak
# - answers with Ollama chat (qwen3:4b-instruct)
# - *admits when it doesn't have enough info*

import os
import re
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
import faiss
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# -------------------- CONFIG --------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "mxbai-embed-large")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:1.5b-instruct")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", os.path.join(DATA_DIR, "vit_faiss.index"))
META_PATH = os.getenv("META_PATH", os.path.join(DATA_DIR, "vit_meta.jsonl"))         # aligned meta per row
IDS_PATH = os.getenv("IDS_PATH", os.path.join(DATA_DIR, "vit_faiss_ids.npy"))        # row -> chunk_id map (optional)

# Retrieval behavior
MIN_GOOD_CHUNKS = 4            # try to get at least this many non-boilerplate chunks
MAX_GOOD_CHUNKS = 6            # keep at most this many
K_STEPS = [15, 35, 60]         # adaptive widening; stops early once enough good chunks
MIN_CONTEXT_CHARS = 600        # if total usable context is less than this, we likely can’t answer
MIN_TOP_SCORE = 0.40           # if best score is too low, likely unrelated (cosine-ish depends on index)

# Timeouts
EMBED_TIMEOUT = 120
CHAT_TIMEOUT = 180

# -------------------- BOILERPLATE FILTER --------------------
# These are tuned for your VIT pages where headers/menus dominate results.
BOILERPLATE_PATTERNS = [
    r"\bApply Now\b",
    r"\bAdmission Info\b",
    r"\bAdmission Enquiry\b",
    r"\bVITEEE\b",
    r"\bVITMEE\b",
    r"\bVITBEE\b",
    r"\bVITLEE\b",
    r"\bVIT Campuses\b",
    r"\bNTTM\b",
    r"\bTender\b",
    r"\bCareers\b",
    r"\bB\.Tech\b.*\bApply\b",
    r"\bMBA\b.*\bApply\b",
    r"\bM\.Tech\b.*\bApply\b",
    r"\bM\.C\.A\b.*\bApply\b",
]

def looks_like_boilerplate(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 120:
        return True

    hits = sum(1 for p in BOILERPLATE_PATTERNS if re.search(p, t, flags=re.I))
    if hits >= 3:
        return True

    # lots of pipes / menu-like separators
    if t.count("|") >= 8:
        return True

    # extremely “list-y” navigation blocks
    if t.count(" - Apply Now") >= 2:
        return True

    return False


# -------------------- OLLAMA HELPERS --------------------
def ollama_embed(prompt: str) -> List[float]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": prompt}
    r = requests.post(url, json=payload, timeout=EMBED_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError(f"Ollama embeddings returned no embedding. keys={list(data.keys())}")
    return emb

def ollama_chat(system: str, user: str) -> str:
    """
    Uses Ollama /api/chat (works with qwen3:4b-instruct on your machine).
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # You can tune these if you want
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        }
    }
    r = requests.post(url, json=payload, timeout=CHAT_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    # Ollama returns {"message": {"role": "...", "content": "..."}, ...}
    msg = data.get("message") or {}
    content = msg.get("content")
    if not content:
        # Some versions return "response" for /api/generate; but we're using /api/chat.
        raise RuntimeError(f"Ollama chat returned no content. keys={list(data.keys())}")
    return content.strip()


# -------------------- META LOADING --------------------
def _get_meta_text(rec: Dict[str, Any]) -> str:
    # Be flexible: depending on how you wrote vit_meta.jsonl
    return (
        rec.get("text")
        or rec.get("chunk")
        or rec.get("content")
        or ""
    )

def _get_meta_title(rec: Dict[str, Any]) -> str:
    return (
        rec.get("source_title")
        or rec.get("title")
        or ""
    )

def _get_meta_url(rec: Dict[str, Any]) -> str:
    return (
        rec.get("source_url")
        or rec.get("url")
        or ""
    )

def load_meta_jsonl(path: str) -> List[Dict[str, Any]]:
    meta: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            meta.append(json.loads(line))
    return meta


# -------------------- RETRIEVAL --------------------
def retrieve_context(
    question: str,
    index: faiss.Index,
    meta: List[Dict[str, Any]],
    row_to_chunk_id: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Adaptive retrieval:
    - embed question
    - search with increasing K
    - filter boilerplate
    - stop once we have enough good chunks
    """
    qvec = np.array([ollama_embed(question)], dtype="float32")

    best_top_score: float = -1.0
    chosen_hits: List[Dict[str, Any]] = []
    chosen_context_parts: List[str] = []

    for k in K_STEPS:
        scores, rows = index.search(qvec, k)
        rows0 = rows[0]
        scores0 = scores[0]

        # Track top score for “is this even related?”
        if len(scores0) > 0:
            best_top_score = max(best_top_score, float(scores0[0]))

        hits: List[Dict[str, Any]] = []
        context_parts: List[str] = []

        for row, score in zip(rows0, scores0):
            if row < 0:
                continue
            row_i = int(row)
            if row_i >= len(meta):
                continue

            rec = meta[row_i]
            txt = _get_meta_text(rec)

            if looks_like_boilerplate(txt):
                continue

            if len(txt.split()) < 40:
                continue

            txt_short = txt[:800]

            chunk_id = None
            if row_to_chunk_id is not None and row_i < len(row_to_chunk_id):
                chunk_id = int(row_to_chunk_id[row_i])
            else:
                # fallback if meta already includes chunk id
                if "id" in rec:
                    try:
                        chunk_id = int(rec["id"])
                    except Exception:
                        chunk_id = None

            hits.append({
                "score": float(score),
                "row": row_i,
                "chunk_id": chunk_id,
                "title": _get_meta_title(rec),
                "url": _get_meta_url(rec),
                "preview": (txt[:260] + "…") if len(txt) > 260 else txt,
            })
            context_parts.append(
                f"[chunk_id={chunk_id}] {_get_meta_title(rec)}\nURL: {_get_meta_url(rec)}\n{txt_short}"
            )

            if len(hits) >= MAX_GOOD_CHUNKS:
                break

        # If we got enough good chunks, accept this K
        total_context_chars = sum(len(p) for p in context_parts)
        if len(hits) >= MIN_GOOD_CHUNKS and total_context_chars >= MIN_CONTEXT_CHARS:
            chosen_hits = hits
            chosen_context_parts = context_parts
            break

        # Otherwise keep the best attempt so far, then widen K
        # Prefer the attempt with more usable context
        if len(context_parts) > len(chosen_context_parts):
            chosen_hits = hits
            chosen_context_parts = context_parts

    return {
        "top_score": best_top_score,
        "hits": chosen_hits,
        "context": "\n\n---\n\n".join(chosen_context_parts),
    }


# -------------------- FASTAPI APP --------------------
app = FastAPI(title="CampusBot (VIT) - Local RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev; tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str
    k: Optional[int] = None  # optional override, not required

class AskResponse(BaseModel):
    answer: str
    had_enough_info: bool
    top_score: float
    sources: List[Dict[str, Any]]


# Lazy globals
INDEX: Optional[faiss.Index] = None
META: Optional[List[Dict[str, Any]]] = None
ROW_TO_CHUNK: Optional[np.ndarray] = None

def ensure_loaded() -> None:
    global INDEX, META, ROW_TO_CHUNK

    if INDEX is None:
        if not os.path.exists(FAISS_INDEX_PATH):
            raise FileNotFoundError(f"Missing FAISS index: {FAISS_INDEX_PATH}")
        INDEX = faiss.read_index(FAISS_INDEX_PATH)

    if META is None:
        if not os.path.exists(META_PATH):
            raise FileNotFoundError(f"Missing meta file: {META_PATH}")
        META = load_meta_jsonl(META_PATH)

    if ROW_TO_CHUNK is None:
        if os.path.exists(IDS_PATH):
            ROW_TO_CHUNK = np.load(IDS_PATH)
        else:
            ROW_TO_CHUNK = None


@app.get("/health")
def health() -> Dict[str, Any]:
    ensure_loaded()
    assert INDEX is not None
    return {
        "ok": True,
        "faiss_ntotal": int(INDEX.ntotal),
        "meta_rows": len(META or []),
        "embed_model": EMBED_MODEL,
        "chat_model": CHAT_MODEL,
    }


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    ensure_loaded()
    assert INDEX is not None
    assert META is not None

    question = (req.question or "").strip()
    if not question:
        return AskResponse(
            answer="Ask me something 🙂",
            had_enough_info=False,
            top_score=0.0,
            sources=[],
        )

    # If user explicitly passes k, we can override K_STEPS by using [k] only.
    # But we still keep filtering + “admit lack of info” logic.
    global K_STEPS
    if req.k is not None and req.k > 0:
        local_steps = [int(req.k)]
    else:
        local_steps = K_STEPS

    # Use a small trick: temporarily use local steps without mutating global
    original_steps = K_STEPS
    try:
        K_STEPS = local_steps
        retrieved = retrieve_context(question, INDEX, META, ROW_TO_CHUNK)
    finally:
        K_STEPS = original_steps

    top_score = float(retrieved["top_score"])
    hits = retrieved["hits"]
    context = retrieved["context"]

    # Decide if we “have enough info”
    had_enough_info = True
    if len(context.strip()) < MIN_CONTEXT_CHARS:
        had_enough_info = False
    if top_score >= 0 and top_score < MIN_TOP_SCORE:
        # low similarity overall => probably not in corpus
        had_enough_info = False
    if len(hits) < 3:
        had_enough_info = False

    # If not enough info, be honest + show what we found (sources)
    if not had_enough_info:
        answer = (
            "I couldn’t find enough *reliable* information in my current VIT Chennai knowledge base "
            "to answer that confidently.\n\n"
            "What I *did* find looks like navigation/summary text or only loosely related pages.\n"
            "If you want, try rephrasing with more details (programme name, year, exam name like VITMEE, etc.)."
        )
        return AskResponse(
            answer=answer,
            had_enough_info=False,
            top_score=top_score if top_score >= 0 else 0.0,
            sources=[{k: v for k, v in h.items() if k in ("score", "chunk_id", "title", "url")} for h in hits[:8]],
        )

    # Otherwise, ask the LLM to answer strictly from context
    system = (
        "You are CampusBot for VIT Chennai.\n"
        "Answer ONLY using the provided CONTEXT.\n"
        "If the context does NOT contain the answer, say:\n"
        "\"I don't have enough information in my knowledge base to answer that.\"\n"
        "Be concise, use bullet points when helpful.\n"
        "If you mention requirements/steps, make sure they appear in the context.\n"
    )

    user = (
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT:\n{context}\n\n"
        "Now answer the QUESTION using only the CONTEXT. "
        "If insufficient, admit it."
    )

    try:
        answer = ollama_chat(system=system, user=user)
    except Exception as e:
        # Fail-safe: still return retrieval + honest error
        return AskResponse(
            answer=f"LLM generation failed: {e}",
            had_enough_info=False,
            top_score=top_score,
            sources=[{k: v for k, v in h.items() if k in ("score", "chunk_id", "title", "url")} for h in hits[:8]],
        )

    # Extra guard: if model ignored instructions, enforce honesty
    # If answer is suspiciously generic AND we had limited context, force disclaimer.
    if len(context.strip()) < (MIN_CONTEXT_CHARS + 200) and len(answer) > 900:
        answer = (
            "I don't have enough information in my knowledge base to answer that.\n\n"
            "Here are the closest sources I found:\n"
            + "\n".join([f"- {_safe(h.get('title'))} ({h.get('url')})" for h in hits[:6]])
        )
        had_enough_info = False

    return AskResponse(
        answer=answer,
        had_enough_info=True,
        top_score=top_score,
        sources=[{k: v for k, v in h.items() if k in ("score", "chunk_id", "title", "url")} for h in hits[:8]],
    )


def _safe(x: Any) -> str:
    try:
        return str(x or "").strip()
    except Exception:
        return ""


# Run:
#   uvicorn server:app --reload
# Or:
#   python3 -m uvicorn server:app 