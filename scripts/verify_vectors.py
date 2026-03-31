import json
import os
from collections import Counter

CHUNKS_PATH = "vit_chunks.jsonl"
EMBED_PATH = "vit_embeddings.jsonl"
FAIL_PATH = "vit_failed_embeddings.jsonl"   # your failure log
STATE_PATH = "vit_vector_state.json"
CORPUS_PATH = "vit_corpus.jsonl"

def read_ids(path):
    ids = []
    if not os.path.exists(path):
        return ids
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "id" in obj:
                    ids.append(int(obj["id"]))
            except Exception:
                continue
    return ids

def wc_lines(path):
    c = 0
    with open(path, "r", encoding="utf-8") as f:
        for _ in f:
            c += 1
    return c

def load_state():
    if not os.path.exists(STATE_PATH):
        return None
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    corpus_lines = wc_lines(CORPUS_PATH) if os.path.exists(CORPUS_PATH) else None
    state = load_state()

    chunk_ids = read_ids(CHUNKS_PATH)
    embed_ids = read_ids(EMBED_PATH)
    fail_ids  = read_ids(FAIL_PATH)

    chunk_set = set(chunk_ids)
    embed_set = set(embed_ids)
    fail_set  = set(fail_ids)

    # duplicates
    dup_chunks = [i for i, c in Counter(chunk_ids).items() if c > 1]
    dup_embeds = [i for i, c in Counter(embed_ids).items() if c > 1]
    dup_fails  = [i for i, c in Counter(fail_ids).items() if c > 1]

    # coverage checks
    # If your script writes chunks for ALL attempts (recommended), then:
    missing_for_chunks = sorted(chunk_set - (embed_set | fail_set))
    extra_embeds = sorted(embed_set - chunk_set)
    extra_fails  = sorted(fail_set - chunk_set)

    print("=== CORPUS PROGRESS ===")
    if corpus_lines is not None:
        print(f"Corpus lines total: {corpus_lines}")
    if state:
        print(f"State corpus_line: {state.get('corpus_line')}")
        print(f"State global_chunk_id: {state.get('global_chunk_id')}")
    print()

    print("=== FILE COUNTS ===")
    print(f"Chunks lines: {len(chunk_ids)} (unique {len(chunk_set)})")
    print(f"Embeddings lines: {len(embed_ids)} (unique {len(embed_set)})")
    print(f"Failed lines: {len(fail_ids)} (unique {len(fail_set)})")
    print()

    print("=== DUPLICATES ===")
    print(f"Duplicate chunk IDs: {len(dup_chunks)}")
    print(f"Duplicate embed IDs: {len(dup_embeds)}")
    print(f"Duplicate fail IDs: {len(dup_fails)}")
    print()

    print("=== COVERAGE (important) ===")
    print(f"Chunks with NO embed AND NO fail log: {len(missing_for_chunks)}")
    if missing_for_chunks[:10]:
        print("First few missing IDs:", missing_for_chunks[:10])

    print(f"Embeddings whose id is not present in chunks: {len(extra_embeds)}")
    if extra_embeds[:10]:
        print("First few extra embed IDs:", extra_embeds[:10])

    print(f"Fails whose id is not present in chunks: {len(extra_fails)}")
    if extra_fails[:10]:
        print("First few extra fail IDs:", extra_fails[:10])

    print()
    ok_coverage = (len(missing_for_chunks) == 0)
    print("✅ PASS" if ok_coverage else "❌ FAIL")
    if not ok_coverage:
        print("Fix: re-run a small script to regenerate/repair missing IDs, or ensure you log failures for every attempt.")

if __name__ == "__main__":
    main()
