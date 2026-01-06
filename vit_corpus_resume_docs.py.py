import os
import json
import time
from urllib.parse import urlparse

import requests
import urllib3
from pypdf import PdfReader

# ------------ CONFIG ------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RESOURCES_FILE = os.path.join(BASE_DIR, "vit_chennai_other_resources.txt")
DOWNLOAD_ROOT = os.path.join(BASE_DIR, "vit_site_data")
CORPUS_PATH = os.path.join(BASE_DIR, "vit_corpus.jsonl")

DOC_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}

START_DOC_INDEX = 404   # <-- we resume from DOC 404 based on your log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ------------ HELPERS ------------

def get_extension(url: str) -> str:
    path = urlparse(url).path
    if not path:
        return ""
    filename = os.path.basename(path)
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def make_local_path(url: str, download_root: str, default_ext: str | None = None) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc or "chennai.vit.ac.in"
    path = parsed.path

    if not path or path.endswith("/"):
        dir_path = os.path.join(download_root, netloc, path.lstrip("/"))
        filename = "index"
        if default_ext:
            filename += f".{default_ext}"
        else:
            filename += ".html"
    else:
        dir_path = os.path.join(download_root, netloc, os.path.dirname(path.lstrip("/")))
        filename = os.path.basename(path)
        if "." not in filename and default_ext:
            filename = f"{filename}.{default_ext}"

    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, filename)


def extract_pdf_text(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(pages_text)
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)
    except Exception as e:
        print(f"  ! Error extracting PDF text from {pdf_path}: {e}")
        return ""


def load_urls(filename: str):
    urls = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url:
                urls.append(url)
    return urls


def sanitize_text(s: str) -> str:
    if s is None:
        return ""
    return s.encode("utf-8", errors="replace").decode("utf-8")


def write_corpus_entry_append(url: str, doc_type: str, title: str, local_path: str, text: str):
    record = {
        "url": sanitize_text(url),
        "type": doc_type,
        "title": sanitize_text(title),
        "local_path": sanitize_text(local_path),
        "text": sanitize_text(text),
    }
    with open(CORPUS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ------------ MAIN RESUME LOGIC ------------

def main():
    resource_urls = load_urls(RESOURCES_FILE)

    # same filter as the original script
    doc_urls = []
    for url in resource_urls:
        ext = get_extension(url)
        if ext in DOC_EXTENSIONS:
            doc_urls.append(url)

    print(f"Total document URLs: {len(doc_urls)}")
    print(f"Resuming from DOC index {START_DOC_INDEX} ...")

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "VITChennaiCorpusBuilder/1.0 (+university project)"}
    )

    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

    total = len(doc_urls)
    processed = 0

    for i, url in enumerate(doc_urls, start=1):
        if i < START_DOC_INDEX:
            continue  # skip ones already done

        ext = get_extension(url)
        print(f"[DOC {i}/{total}] {url} (. {ext})")

        if ext != "pdf":
            print("  ! Non-PDF doc type, skipping text extraction for now.")
            continue

        try:
            resp = session.get(url, timeout=30, stream=True, verify=False)
        except Exception as e:
            print(f"  ! Error fetching {url}: {e}")
            continue

        if resp.status_code != 200:
            print(f"  ! Skipped {url} (status {resp.status_code})")
            continue

        local_path = make_local_path(url, DOWNLOAD_ROOT)

        try:
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            print(f"  ! Error saving PDF {local_path}: {e}")
            continue

        text = extract_pdf_text(local_path)
        if not text.strip():
            print("  ! No text extracted from PDF, skipping corpus entry.")
            continue

        title = os.path.basename(local_path)

        write_corpus_entry_append(
            url=url,
            doc_type="pdf",
            title=title,
            local_path=local_path,
            text=text,
        )
        processed += 1
        time.sleep(0.03)

    print("\n=== RESUME DONE ===")
    print(f"New PDF documents added to corpus: {processed}")


if __name__ == "__main__":
    main()
