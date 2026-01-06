import json
import time
import requests
from pathlib import Path

CHUNKS_PATH = Path("vit_chunks.jsonl")
EMBEDS_PATH = Path("vit_embeddings.jsonl")

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "mxbai-embed-large"

SLEEP_BETWEEN = 0.05          # slow down slightly
RETRIES = 6                   # retry per chunk
BACKOFF_BASE = 1.5            # exponential backoff


def ollama_embed(text: str) -> list[float]:
    payload = {"model": EMBED_MODEL, "prompt": text}
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["embedding"]


def load_existing_ids() -> set[int]:
    ids = set()
    if not EMBEDS_PATH.exists():
        return ids
    with EMBEDS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ids.add(int(obj["id"]))
            except Exception:
                # ignore any bad line (rare)
                continue
    return ids


def main():
    if not CHUNKS_PATH.exists():
        print("❌ vit_chunks.jsonl not found in this folder")
        return

    done_ids = load_existing_ids()
    print(f"Already embedded: {len(done_ids)}")

    missing = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            cid = int(obj["id"])
            if cid not in done_ids:
                missing.append(obj)

    print(f"Missing embeddings: {len(missing)}")
    if not missing:
        print("✅ Nothing to do.")
        return

    # Append newly created embeddings
    with EMBEDS_PATH.open("a", encoding="utf-8") as out:
        for idx, chunk_obj in enumerate(missing, start=1):
            cid = int(chunk_obj["id"])
            text = chunk_obj["text"]

            ok = False
            for attempt in range(1, RETRIES + 1):
                try:
                    emb = ollama_embed(text)
                    rec = {
                        "id": cid,
                        "source_url": chunk_obj.get("source_url", ""),
                        "source_title": chunk_obj.get("source_title", ""),
                        "source_type": chunk_obj.get("source_type", ""),
                        "chunk_index": chunk_obj.get("chunk_index", 0),
                        "embedding": emb,
                    }
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    ok = True
                    break
                except Exception as e:
                    wait = (BACKOFF_BASE ** (attempt - 1))
                    print(f"  ! id={cid} attempt {attempt}/{RETRIES} failed: {e} (wait {wait:.1f}s)")
                    time.sleep(wait)

            if not ok:
                print(f"❌ Gave up on chunk id {cid}")

            if idx % 50 == 0:
                print(f"Progress: {idx}/{len(missing)}")
            time.sleep(SLEEP_BETWEEN)

    print("✅ Retry pass finished.")


if __name__ == "__main__":
    main()
