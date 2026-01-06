import json
import os
import time
import requests
from typing import Dict, Any, Set

OLLAMA_BASE_URL = "http://localhost:11434"
EMBED_MODEL = "mxbai-embed-large"

CHUNKS_PATH = "vit_chunks.jsonl"
EMBED_PATH  = "vit_embeddings.jsonl"
FAIL_PATH   = "vit_failed_embeddings.jsonl"

MAX_ATTEMPTS = 1  # <- you asked for ONE attempt
SLEEP_SECONDS = 0.02

def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def read_embeddings_ids() -> Set[int]:
    ids = set()
    if not os.path.exists(EMBED_PATH):
        return ids
    with open(EMBED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    ids.add(int(json.loads(line)["id"]))
                except Exception:
                    pass
    return ids

def load_failed_records() -> Dict[int, Dict[str, Any]]:
    recs = {}
    if not os.path.exists(FAIL_PATH):
        return recs
    with open(FAIL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                cid = int(r["id"])
                if cid not in recs:
                    recs[cid] = r
            except Exception:
                continue
    return recs

def load_chunks_for_ids(target_ids: Set[int]) -> Dict[int, Dict[str, Any]]:
    found = {}
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                cid = int(rec["id"])
                if cid in target_ids and cid not in found:
                    found[cid] = rec
                    if len(found) == len(target_ids):
                        break
            except Exception:
                continue
    return found

def ollama_embed(text: str) -> list:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": text}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError("No embedding returned")
    return emb

def rewrite_failures(remaining: Dict[int, Dict[str, Any]]) -> None:
    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        for cid in sorted(remaining.keys()):
            f.write(json.dumps(remaining[cid], ensure_ascii=False) + "\n")

def main():
    if not os.path.exists(FAIL_PATH):
        print("No failure file found. Nothing to retry.")
        return

    embedded_ids = read_embeddings_ids()
    failed = load_failed_records()

    # Only retry ids that aren't embedded already
    retry_ids = set(failed.keys()) - embedded_ids
    print("Failures in file:", len(failed))
    print("Already embedded (will skip):", len(set(failed.keys()) & embedded_ids))
    print("To retry:", len(retry_ids))

    if not retry_ids:
        print("✅ Nothing to retry.")
        return

    # Need chunk text for retry
    chunks = load_chunks_for_ids(retry_ids)
    missing_text = retry_ids - set(chunks.keys())
    if missing_text:
        print("❌ Some failure ids still have no chunk text record. Example:", sorted(list(missing_text))[:10])
        print("Run reconcile_chunks_and_failures.py first.")
        return

    remaining = dict(failed)
    success = 0

    for cid in sorted(retry_ids):
        rec = chunks[cid]
        text = rec.get("text", "")
        if not text.strip():
            continue

        ok = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                emb = ollama_embed(text)
                emb_record = {
                    "id": cid,
                    "source_url": rec.get("source_url",""),
                    "source_title": rec.get("source_title",""),
                    "source_type": rec.get("source_type",""),
                    "chunk_index": rec.get("chunk_index", 0),
                    "embedding": emb,
                    "retried": True
                }
                append_jsonl(EMBED_PATH, emb_record)
                ok = True
                break
            except Exception as e:
                print(f"  ❌ still failing id={cid} attempt={attempt}: {e}")

        if ok:
            success += 1
            remaining.pop(cid, None)

        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    rewrite_failures(remaining)
    print(f"\n✅ Retried done. Success={success}. Remaining failures={len(remaining)}")

if __name__ == "__main__":
    main()
