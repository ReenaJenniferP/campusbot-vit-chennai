import os
import json
import time
import requests
from typing import List, Dict, Any, Optional

# ---------------- CONFIG ----------------
CORPUS_PATH = "vit_corpus.jsonl"

CHUNKS_PATH = "vit_chunks.jsonl"
EMBED_PATH = "vit_embeddings.jsonl"
FAILED_PATH = "vit_failed_embeddings.jsonl"   # <-- NEW (logs failures)
STATE_PATH = "vit_vector_state.json"

OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "mxbai-embed-large"

CHUNK_WORDS = 220
OVERLAP_WORDS = 40

SLEEP_SECONDS = 0.02


# ---------------- HELPERS ----------------
def sanitize_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    return s.encode("utf-8", errors="replace").decode("utf-8")


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_state() -> Dict[str, Any]:
    """
    Resume safely even if you stop mid-document.
    corpus_line: which line in vit_corpus.jsonl
    chunk_in_doc: which chunk index within that corpus line
    global_chunk_id: next global id to use
    """
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"corpus_line": 0, "chunk_in_doc": 0, "global_chunk_id": 0}


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_last_id(path: str) -> Optional[int]:
    """Read last non-empty JSONL line and return its 'id'."""
    if not os.path.exists(path):
        return None
    last = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    if not last:
        return None
    try:
        return int(json.loads(last)["id"])
    except Exception:
        return None


def chunk_words(text: str, chunk_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    step = max(1, chunk_words - overlap_words)

    for start in range(0, len(words), step):
        end = start + chunk_words
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break

    return chunks


def ollama_embed_one_try(prompt: str, model: str) -> List[float]:
    """
    ONE attempt only. If it fails, raise immediately so caller can log + skip.
    """
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": model, "prompt": prompt}

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()

    data = r.json()
    emb = data.get("embedding")
    if not emb:
        raise ValueError(f"No embedding returned. Keys: {list(data.keys())}")
    return emb



# ---------------- MAIN ----------------
def main():
    # Ensure files exist
    for p in [CHUNKS_PATH, EMBED_PATH, FAILED_PATH]:
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").close()

    if not os.path.exists(CORPUS_PATH):
        raise FileNotFoundError(f"Can't find {CORPUS_PATH} in this folder.")

    state = load_state()

    # --- Align global_chunk_id so we don't re-use old IDs (prevents duplicates) ---
    last_chunk_id = get_last_id(CHUNKS_PATH)
    last_emb_id = get_last_id(EMBED_PATH)

    suggested_next = 0
    if last_chunk_id is not None:
        suggested_next = max(suggested_next, last_chunk_id + 1)
    if last_emb_id is not None:
        suggested_next = max(suggested_next, last_emb_id + 1)

    if int(state.get("global_chunk_id", 0)) < suggested_next:
        print(f"⚠️ State global_chunk_id ({state.get('global_chunk_id')}) behind file tail.")
        print(f"✅ Auto-fixing global_chunk_id -> {suggested_next}")
        state["global_chunk_id"] = suggested_next
        save_state(state)

    start_line = int(state.get("corpus_line", 0))
    start_chunk_in_doc = int(state.get("chunk_in_doc", 0))
    global_chunk_id = int(state.get("global_chunk_id", 0))

    print("=== Chunk + Vectorize (FAST-SKIP) ===")
    print(f"Corpus: {CORPUS_PATH}")
    print(f"Embedding model: {EMBED_MODEL}")
    print(f"Resuming from corpus line: {start_line}")
    print(f"Resuming chunk_in_doc: {start_chunk_in_doc}")
    print(f"Starting global_chunk_id: {global_chunk_id}")
    print()

    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        # Skip already processed corpus lines
        for _ in range(start_line):
            next(f, None)

        for line_idx, line in enumerate(f, start=start_line):
            line = line.strip()
            if not line:
                state.update({"corpus_line": line_idx + 1, "chunk_in_doc": 0})
                save_state(state)
                continue

            try:
                doc = json.loads(line)
            except Exception:
                state.update({"corpus_line": line_idx + 1, "chunk_in_doc": 0})
                save_state(state)
                continue

            url = sanitize_text(doc.get("url", ""))
            title = sanitize_text(doc.get("title", ""))
            doc_type = sanitize_text(doc.get("type", ""))
            text = sanitize_text(doc.get("text", ""))

            if not text.strip():
                state.update({"corpus_line": line_idx + 1, "chunk_in_doc": 0})
                save_state(state)
                continue

            chunks = chunk_words(text, CHUNK_WORDS, OVERLAP_WORDS)
            if not chunks:
                state.update({"corpus_line": line_idx + 1, "chunk_in_doc": 0})
                save_state(state)
                continue

            # If resuming within this same doc line, start from chunk_in_doc; else 0
            local_start = start_chunk_in_doc if line_idx == start_line else 0

            print(f"[Line {line_idx}] {doc_type} | {title} | chunks={len(chunks)} | starting_at={local_start}")

            for local_i in range(local_start, len(chunks)):
                chunk = chunks[local_i]
                chunk_id = global_chunk_id

                chunk_record = {
                    "id": chunk_id,
                    "source_url": url,
                    "source_title": title,
                    "source_type": doc_type,
                    "chunk_index": local_i,
                    "text": chunk,
                }

                # Always write chunk (so we can retry missing embeddings later)
                append_jsonl(CHUNKS_PATH, chunk_record)

                # Try embedding (2 attempts max)
                try:
                    emb = ollama_embed_one_try(chunk, EMBED_MODEL)
                    emb_record = {
                        "id": chunk_id,
                        "source_url": url,
                        "source_title": title,
                        "source_type": doc_type,
                        "chunk_index": local_i,
                        "embedding": emb,
                    }
                    append_jsonl(EMBED_PATH, emb_record)

                except Exception as e:
                    # Log failure, then MOVE ON
                    fail_record = {
                        "id": chunk_id,
                        "corpus_line": line_idx,
                        "source_url": url,
                        "source_title": title,
                        "source_type": doc_type,
                        "chunk_index": local_i,
                        "error": str(e),
                        "text": chunk,  # store chunk text so retry script can re-embed
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    append_jsonl(FAILED_PATH, fail_record)
                    print(f"  ❌ Skipped chunk_id={chunk_id} after 2 attempts (logged to {FAILED_PATH})")

                # Advance IDs/state regardless of success
                global_chunk_id += 1
                state["global_chunk_id"] = global_chunk_id

                # Save resume state AFTER each chunk
                state["corpus_line"] = line_idx
                state["chunk_in_doc"] = local_i + 1
                save_state(state)

                if SLEEP_SECONDS:
                    time.sleep(SLEEP_SECONDS)

            # Finished whole doc line
            state["corpus_line"] = line_idx + 1
            state["chunk_in_doc"] = 0
            save_state(state)

    print("\n✅ Done!")
    print(f"Chunks:      {CHUNKS_PATH}")
    print(f"Embeddings:  {EMBED_PATH}")
    print(f"Failures:    {FAILED_PATH}")
    print(f"State:       {STATE_PATH}")


if __name__ == "__main__":
    main()
