import os
import json
import sqlite3
import numpy as np
from tqdm import tqdm

# ---- CONFIG ----
CHUNKS_JSONL = "vit_chunks.jsonl"
EMB_JSONL = "vit_embeddings.jsonl"

CHUNKS_DB = "vit_chunks.sqlite"
FAISS_INDEX_PATH = "vit_faiss.index"
FAISS_IDS_PATH = "vit_faiss_ids.npy"
META_JSONL = "vit_meta.jsonl"

BATCH_INSERT = 2000
PROGRESS_EVERY = 5000

def ensure_chunks_sqlite():
    """Create sqlite db from vit_chunks.jsonl if not already present."""
    if os.path.exists(CHUNKS_DB) and os.path.getsize(CHUNKS_DB) > 0:
        return

    if not os.path.exists(CHUNKS_JSONL):
        raise FileNotFoundError(f"Missing {CHUNKS_JSONL}")

    print(f"🔧 Building {CHUNKS_DB} from {CHUNKS_JSONL} ...")

    conn = sqlite3.connect(CHUNKS_DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            source_url TEXT,
            source_title TEXT,
            source_type TEXT,
            chunk_index INTEGER,
            text TEXT
        )
    """)
    conn.commit()

    batch = []
    inserted = 0

    with open(CHUNKS_JSONL, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Reading chunks"):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            batch.append((
                int(obj["id"]),
                obj.get("source_url", ""),
                obj.get("source_title", ""),
                obj.get("source_type", ""),
                int(obj.get("chunk_index", 0)),
                obj.get("text", "")
            ))

            if len(batch) >= BATCH_INSERT:
                cur.executemany("""
                    INSERT OR REPLACE INTO chunks
                    (id, source_url, source_title, source_type, chunk_index, text)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                inserted += len(batch)
                batch.clear()

    if batch:
        cur.executemany("""
            INSERT OR REPLACE INTO chunks
            (id, source_url, source_title, source_type, chunk_index, text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()
        inserted += len(batch)

    conn.close()
    print(f"✅ chunks sqlite ready. rows_inserted={inserted}")

def l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization for cosine similarity via inner product."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms

def build_index():
    if not os.path.exists(EMB_JSONL):
        raise FileNotFoundError(f"Missing {EMB_JSONL}")
    ensure_chunks_sqlite()

    # Import FAISS only after install is confirmed
    import faiss

    conn = sqlite3.connect(CHUNKS_DB)
    cur = conn.cursor()

    # We’ll collect vectors in a list, then stack at end (safe + simple)
    vectors = []
    id_list = []

    # Fresh meta output
    if os.path.exists(META_JSONL):
        os.remove(META_JSONL)

    print(f"📦 Reading embeddings from {EMB_JSONL} ...")
    dim = None
    count = 0
    missing_in_db = 0

    with open(EMB_JSONL, "r", encoding="utf-8") as f, open(META_JSONL, "a", encoding="utf-8") as meta_out:
        for line in tqdm(f, desc="Embeddings"):
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)
            cid = int(obj["id"])
            emb = obj.get("embedding")

            if emb is None:
                continue

            v = np.asarray(emb, dtype=np.float32)
            if dim is None:
                dim = int(v.shape[0])
            elif int(v.shape[0]) != dim:
                raise ValueError(f"Embedding dim mismatch at id={cid}. Expected {dim}, got {v.shape[0]}")

            # fetch chunk text/metadata from sqlite
            cur.execute("SELECT source_url, source_title, source_type, chunk_index, text FROM chunks WHERE id=?", (cid,))
            row = cur.fetchone()
            if not row:
                # Should not happen after your reconcile script, but we handle it
                missing_in_db += 1
                continue

            source_url, source_title, source_type, chunk_index, text = row

            vectors.append(v)
            id_list.append(cid)

            meta_record = {
                "id": cid,
                "source_url": source_url,
                "source_title": source_title,
                "source_type": source_type,
                "chunk_index": chunk_index,
                "text": text,
            }
            meta_out.write(json.dumps(meta_record, ensure_ascii=False) + "\n")

            count += 1
            if count % PROGRESS_EVERY == 0:
                tqdm.write(f"… loaded {count} embeddings")

    conn.close()

    if not vectors:
        raise RuntimeError("No vectors loaded. Check vit_embeddings.jsonl format.")

    X = np.vstack(vectors)  # (N, D)
    X = l2_normalize(X)

    print(f"✅ Loaded vectors: N={X.shape[0]}, D={X.shape[1]}")
    if missing_in_db:
        print(f"⚠️ Embeddings skipped because chunk id not found in sqlite: {missing_in_db}")

    # Build FAISS index for cosine similarity (normalized + inner product)
    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)

    faiss.write_index(index, FAISS_INDEX_PATH)
    np.save(FAISS_IDS_PATH, np.asarray(id_list, dtype=np.int64))

    print("\n✅ FAISS build complete")
    print(f"Index: {FAISS_INDEX_PATH}")
    print(f"Row->chunk_id map: {FAISS_IDS_PATH}")
    print(f"Aligned meta: {META_JSONL}")
    print(f"Chunk DB: {CHUNKS_DB}")
    print(f"Total indexed: {index.ntotal}")

if __name__ == "__main__":
    build_index()
