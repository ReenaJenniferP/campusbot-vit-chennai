import json
import numpy as np
import requests
import faiss

FAISS_INDEX_PATH = "vit_faiss.index"
IDS_PATH = "vit_faiss_ids.npy"
META_PATH = "vit_meta.jsonl"

OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "mxbai-embed-large"

TOP_K = 5

def embed_query(q: str) -> np.ndarray:
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": q},
        timeout=120,
    )
    r.raise_for_status()
    emb = r.json().get("embedding")
    if not emb:
        raise RuntimeError("No embedding returned from Ollama.")
    v = np.asarray(emb, dtype=np.float32)
    # normalize for cosine similarity
    v = v / (np.linalg.norm(v) + 1e-12)
    return v

def load_meta_lines(path: str):
    # simple: load all meta in memory (72608 lines is fine)
    meta = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                meta.append(json.loads(line))
    return meta

def main():
    index = faiss.read_index(FAISS_INDEX_PATH)
    ids = np.load(IDS_PATH)  # row -> chunk_id
    meta = load_meta_lines(META_PATH)  # row-aligned

    print("✅ Loaded index:", index.ntotal)

    while True:
        q = input("\nAsk > ").strip()
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break

        v = embed_query(q).reshape(1, -1)
        scores, rows = index.search(v, TOP_K)

        print("\n--- Results ---")
        for rank, (row, score) in enumerate(zip(rows[0], scores[0]), start=1):
            if row < 0:
                continue
            rec = meta[int(row)]
            print(f"\n#{rank} score={score:.4f}  id={rec['id']}")
            print(f"title: {rec.get('source_title','')}")
            print(f"url:   {rec.get('source_url','')}")
            print("text:")
            print(rec.get("text","")[:500], "..." if len(rec.get("text","")) > 500 else "")

if __name__ == "__main__":
    main()
