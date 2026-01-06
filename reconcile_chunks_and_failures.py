import json
import os
from typing import Dict, Any, Optional, List, Set

CORPUS_PATH = "vit_corpus.jsonl"
CHUNKS_PATH = "vit_chunks.jsonl"
EMBED_PATH  = "vit_embeddings.jsonl"
FAIL_PATH   = "vit_failed_embeddings.jsonl"
STATE_PATH  = "vit_vector_state.json"

CHUNK_WORDS = 220
OVERLAP_WORDS = 40

def sanitize_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    return s.encode("utf-8", errors="replace").decode("utf-8")

def chunk_words(text: str, chunk_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, chunk_words - overlap_words)
    for start in range(0, len(words), step):
        end = start + chunk_words
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
    return chunks

def read_ids_jsonl(path: str) -> Set[int]:
    ids = set()
    if not os.path.exists(path):
        return ids
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(int(json.loads(line)["id"]))
            except Exception:
                pass
    return ids

def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def load_state_max_id() -> int:
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        st = json.load(f)
    # global_chunk_id is "next id to use"
    return int(st["global_chunk_id"]) - 1

def load_chunk_records_for_ids(target_ids: Set[int]) -> Dict[int, Dict[str, Any]]:
    """Scan chunks file once, return records for only target ids."""
    found = {}
    if not os.path.exists(CHUNKS_PATH):
        return found
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

def normalize_failures(remove_ids: Set[int] = set(), add_records: List[Dict[str, Any]] = []):
    """Rewrite vit_failed_embeddings.jsonl, remove duplicates, remove ids, add new records."""
    merged: Dict[int, Dict[str, Any]] = {}

    if os.path.exists(FAIL_PATH):
        with open(FAIL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    cid = int(rec["id"])
                    if cid in remove_ids:
                        continue
                    if cid not in merged:
                        merged[cid] = rec
                except Exception:
                    continue

    for rec in add_records:
        cid = int(rec["id"])
        if cid not in remove_ids:
            merged[cid] = rec

    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        for cid in sorted(merged.keys()):
            f.write(json.dumps(merged[cid], ensure_ascii=False) + "\n")

def main():
    if not os.path.exists(CORPUS_PATH):
        raise FileNotFoundError(f"Missing {CORPUS_PATH}")
    if not os.path.exists(STATE_PATH):
        raise FileNotFoundError(f"Missing {STATE_PATH}")

    max_id = load_state_max_id()

    chunk_ids = read_ids_jsonl(CHUNKS_PATH)
    emb_ids   = read_ids_jsonl(EMBED_PATH)
    fail_ids  = read_ids_jsonl(FAIL_PATH)

    all_ids = set(range(0, max_id + 1))

    missing_chunk_records = all_ids - chunk_ids          # these are the 40
    orphan_chunks = chunk_ids - (emb_ids | fail_ids)     # this is your [39767]

    extra_failures = fail_ids - chunk_ids                # should match missing chunk records (40)

    print("=== BEFORE ===")
    print("max_id:", max_id)
    print("chunks:", len(chunk_ids))
    print("embeddings:", len(emb_ids))
    print("failures:", len(fail_ids))
    print("missing chunk records:", len(missing_chunk_records))
    print("orphan chunks (no emb & no fail):", len(orphan_chunks))
    print("extra failures (id not in chunks):", len(extra_failures))
    if orphan_chunks:
        print("example orphan ids:", sorted(list(orphan_chunks))[:10])

    # 1) Rebuild missing chunk records by re-chunking corpus deterministically
    if missing_chunk_records:
        print("\nRebuilding missing chunk records by replaying corpus chunking...")
        needed = set(missing_chunk_records)
        global_chunk_id = 0
        rebuilt = 0

        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except Exception:
                    continue

                url = sanitize_text(doc.get("url", ""))
                title = sanitize_text(doc.get("title", ""))
                doc_type = sanitize_text(doc.get("type", ""))
                text = sanitize_text(doc.get("text", ""))

                chunks = chunk_words(text, CHUNK_WORDS, OVERLAP_WORDS)
                for local_i, chunk in enumerate(chunks):
                    cid = global_chunk_id
                    if cid in needed:
                        chunk_record = {
                            "id": cid,
                            "source_url": url,
                            "source_title": title,
                            "source_type": doc_type,
                            "chunk_index": local_i,
                            "text": chunk,
                            "recovered": True
                        }
                        append_jsonl(CHUNKS_PATH, chunk_record)
                        rebuilt += 1
                        needed.remove(cid)
                        if not needed:
                            break
                    global_chunk_id += 1
                if not needed:
                    break

        print(f"✅ Rebuilt chunk records: {rebuilt}")

    # 2) For orphan chunks, add them into failures so they are “accounted for”
    if orphan_chunks:
        print("\nAdding orphan chunks into failures file so nothing is unaccounted...")
        orphan_recs = load_chunk_records_for_ids(orphan_chunks)
        to_add = []
        for cid in sorted(orphan_chunks):
            rec = orphan_recs.get(cid)
            if not rec:
                # shouldn't happen, but just in case
                to_add.append({"id": cid, "reason": "orphan_chunk_no_record_found"})
            else:
                to_add.append({
                    "id": cid,
                    "source_url": rec.get("source_url",""),
                    "source_title": rec.get("source_title",""),
                    "source_type": rec.get("source_type",""),
                    "chunk_index": rec.get("chunk_index", 0),
                    "reason": "orphan_chunk_missing_embedding_and_failure"
                })
        normalize_failures(add_records=to_add)
        print(f"✅ Added orphan ids to failures: {len(to_add)}")

    # 3) Recompute and show AFTER
    chunk_ids2 = read_ids_jsonl(CHUNKS_PATH)
    emb_ids2   = read_ids_jsonl(EMBED_PATH)
    fail_ids2  = read_ids_jsonl(FAIL_PATH)

    missing2 = (set(range(0, max_id + 1)) - chunk_ids2)
    extra_fail2 = fail_ids2 - chunk_ids2
    orphan2 = chunk_ids2 - (emb_ids2 | fail_ids2)

    print("\n=== AFTER ===")
    print("chunks:", len(chunk_ids2))
    print("embeddings:", len(emb_ids2))
    print("failures:", len(fail_ids2))
    print("missing chunk records:", len(missing2))
    print("extra failures:", len(extra_fail2))
    print("orphan chunks:", len(orphan2))

    if missing2:
        print("Example missing:", sorted(list(missing2))[:10])
    if extra_fail2:
        print("Example extra failures:", sorted(list(extra_fail2))[:10])
    if orphan2:
        print("Example orphan:", sorted(list(orphan2))[:10])

if __name__ == "__main__":
    main()
