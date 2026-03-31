import os
import json
import time
from urllib.parse import urlparse
import requests
import urllib3
from bs4 import BeautifulSoup
from pypdf import PdfReader

# -------- CONFIG --------
DOWNLOAD_ROOT = "vit_site_data"       # where raw files are stored
CORPUS_PATH = "vit_corpus.jsonl"      # AI-usable text corpus

DOC_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}

# Disable SSL warnings because we'll use verify=False for this domain
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# -------- UTILS --------
def get_extension(url: str) -> str:
    """Return lowercase file extension like 'pdf', 'jpg', or '' if none."""
    path = urlparse(url).path
    if not path:
        return ""
    filename = os.path.basename(path)
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def make_local_path(url: str, download_root: str, default_ext: str | None = None) -> str:
    """
    Map a URL to a local file path, creating directories as needed.
    If there's no extension and default_ext is provided, use that.
    """
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
        # If no extension in filename and default_ext provided, add it
        if "." not in filename and default_ext:
            filename = f"{filename}.{default_ext}"

    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, filename)


def clean_html(html_text: str) -> tuple[str, str]:
    """
    Given raw HTML, return (title, plain_text).
    Removes scripts/styles/nav/footer-ish stuff as a basic cleanup.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # Remove script/style tags completely
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Optional: remove common layout tags if they have little content
    for tag_name in ["nav", "footer"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    text = soup.get_text(separator="\n")
    # Basic cleanup: strip lines, remove empties
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]  # remove blank lines
    clean_text = "\n".join(lines)

    return title, clean_text


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF file using pypdf."""
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
    """Load non-empty, stripped URLs from a text file."""
    urls = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url:
                urls.append(url)
    return urls


def write_corpus_entry(f, url: str, doc_type: str, title: str, local_path: str, text: str):
    """Write a single JSONL record to the corpus file."""
    record = {
        "url": url,
        "type": doc_type,  # "html" or "pdf"
        "title": title,
        "local_path": local_path,
        "text": text,
    }
    f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -------- MAIN PIPELINE --------
def main():
    # 1) Load URLs
    page_urls = load_urls("vit_chennai_pages.txt")
    resource_urls = load_urls("vit_chennai_other_resources.txt")

    print(f"Loaded {len(page_urls)} HTML-like page URLs.")
    print(f"Loaded {len(resource_urls)} other resource URLs.")

    # Filter other resources to only document-like (we'll primarily handle PDFs fully)
    doc_urls = []
    for url in resource_urls:
        ext = get_extension(url)
        if ext in DOC_EXTENSIONS:
            doc_urls.append(url)

    print(f"Filtered to {len(doc_urls)} document URLs (pdf/doc/etc.).")

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "VITChennaiCorpusBuilder/1.0 (+university project)"}
    )

    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

    # Open corpus file for writing
    with open(CORPUS_PATH, "w", encoding="utf-8") as corpus_file:
        # 2) Process HTML pages
        print("\n=== PROCESSING HTML PAGES ===")
        html_success = 0

        for i, url in enumerate(page_urls, start=1):
            print(f"[HTML {i}/{len(page_urls)}] {url}")
            try:
                resp = session.get(url, timeout=25, verify=False)
            except Exception as e:
                print(f"  ! Error fetching {url}: {e}")
                continue

            if resp.status_code != 200:
                print(f"  ! Skipped {url} (status {resp.status_code})")
                continue

            local_path = make_local_path(url, DOWNLOAD_ROOT, default_ext="html")
            try:
                # Save raw HTML
                with open(local_path, "w", encoding="utf-8", errors="ignore") as f:
                    f.write(resp.text)
            except Exception as e:
                print(f"  ! Error saving HTML file {local_path}: {e}")
                continue

            # Extract clean text
            try:
                title, clean_text = clean_html(resp.text)
            except Exception as e:
                print(f"  ! Error parsing/cleaning HTML from {url}: {e}")
                continue

            if not clean_text.strip():
                print("  ! No text extracted, skipping corpus entry.")
                continue

            write_corpus_entry(
                corpus_file,
                url=url,
                doc_type="html",
                title=title,
                local_path=local_path,
                text=clean_text,
            )
            html_success += 1
            time.sleep(0.03)

        print(f"HTML pages successfully added to corpus: {html_success}/{len(page_urls)}")

        # 3) Process document URLs (focus on PDFs)
        print("\n=== PROCESSING DOCUMENTS (PDFs primarily) ===")
        doc_success = 0

        for i, url in enumerate(doc_urls, start=1):
            ext = get_extension(url)
            print(f"[DOC {i}/{len(doc_urls)}] {url} (.{ext})")

            # We'll fully process only PDFs (text extraction).
            if ext != "pdf":
                print("  ! Non-PDF document type, skipping text extraction for now.")
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
                # Save PDF file
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                print(f"  ! Error saving PDF {local_path}: {e}")
                continue

            # Extract text from PDF
            text = extract_pdf_text(local_path)
            if not text.strip():
                print("  ! No text extracted from PDF, skipping corpus entry.")
                continue

            # Title: use filename as basic title
            title = os.path.basename(local_path)
            write_corpus_entry(
                corpus_file,
                url=url,
                doc_type="pdf",
                title=title,
                local_path=local_path,
                text=text,
            )
            doc_success += 1
            time.sleep(0.03)

        print(f"PDF documents successfully added to corpus: {doc_success}/{len(doc_urls)}")

    print("\n=== ALL DONE ===")
    print(f"Raw files stored under: {os.path.abspath(DOWNLOAD_ROOT)}")
    print(f"Text corpus stored in : {os.path.abspath(CORPUS_PATH)}")


if __name__ == "__main__":
    main()
