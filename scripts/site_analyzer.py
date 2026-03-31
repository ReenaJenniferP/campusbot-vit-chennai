import os
import time
import argparse
from urllib.parse import urlparse, urljoin, urldefrag
from collections import Counter, defaultdict

import requests
from bs4 import BeautifulSoup


START_URL = "https://chennai.vit.ac.in/"
START_DOMAIN = urlparse(START_URL).netloc


def normalize_url(url: str) -> str:
    """Remove fragments and normalize trailing slash."""
    url, _ = urldefrag(url)
    # Remove trailing slash except root
    if url.endswith("/") and len(url) > len("https://a"):
        url = url[:-1]
    return url


def is_same_domain(url: str, domain: str) -> bool:
    try:
        netloc = urlparse(url).netloc
    except Exception:
        return False
    return netloc == domain or netloc == ""


def get_extension(url: str) -> str:
    """Return lowercase file extension like 'pdf', 'jpg', '' (no ext)."""
    path = urlparse(url).path
    if not path:
        return ""
    filename = os.path.basename(path)
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def classify(ext: str, content_type: str) -> str:
    """Rough bucket for each resource."""
    ext = ext.lower()
    ct = (content_type or "").lower()

    if "text/html" in ct or "application/xhtml" in ct or ext in ("html", "htm", ""):
        return "html_pages"

    if ext in ("pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"):
        return "documents"

    if ext in ("jpg", "jpeg", "png", "gif", "webp", "svg", "ico"):
        return "images"

    if ext in ("css",):
        return "stylesheets"

    if ext in ("js",):
        return "scripts"

    if ext in ("woff", "woff2", "ttf", "otf", "eot"):
        return "fonts"

    return "other"


def human_readable_size(num_bytes: int) -> str:
    if num_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def analyze_site(start_url: str, max_pages: int = 500):
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "VITChennaiSiteAnalyzer/1.0 (+university project)"}
    )

    to_visit = [start_url]
    visited = set()

    total_bytes = 0
    total_urls = 0

    size_by_bucket = Counter()
    count_by_bucket = Counter()
    size_by_ext = Counter()
    count_by_ext = Counter()

    while to_visit and len(visited) < max_pages:
        current = normalize_url(to_visit.pop(0))

        if current in visited:
            continue
        if not is_same_domain(current, START_DOMAIN):
            continue

        visited.add(current)
        print(f"[{len(visited)}/{max_pages}] Fetching: {current}")

        try:
            resp = session.get(current, timeout=15, verify=False)
        except Exception as e:
            print(f"  ! Error fetching {current}: {e}")
            continue

        if resp.status_code != 200:
            print(f"  ! Skipped (status {resp.status_code})")
            continue

        # Size estimation
        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
        content_length = resp.headers.get("Content-Length")
        if content_length and content_length.isdigit():
            size = int(content_length)
        else:
            # Fallback: length of body we actually downloaded
            size = len(resp.content or b"")

        ext = get_extension(current)
        bucket = classify(ext, content_type)

        total_urls += 1
        total_bytes += size
        size_by_bucket[bucket] += size
        count_by_bucket[bucket] += 1
        size_by_ext[ext or "(no ext)"] += size
        count_by_ext[ext or "(no ext)"] += 1

        # If it's HTML, parse links and enqueue them
        if bucket == "html_pages":
            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                print(f"  ! Error parsing HTML {current}: {e}")
                soup = None

            if soup is not None:
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                        continue
                    absolute = urljoin(current + "/", href)
                    absolute = normalize_url(absolute)

                    if absolute not in visited and is_same_domain(absolute, START_DOMAIN):
                        to_visit.append(absolute)

        # Be nice to the server
        time.sleep(0.3)

    # ------- SUMMARY -------
    print("\n=== SUMMARY ===")
    print(f"Unique URLs visited  : {len(visited)}")
    print(f"Resources analyzed   : {total_urls}")
    print(f"Estimated total size : {human_readable_size(total_bytes)}\n")

    print("By bucket (type):")
    for bucket, count in count_by_bucket.most_common():
        size = size_by_bucket[bucket]
        print(f"  - {bucket:12s}: {count:4d} items, {human_readable_size(size)}")

    print("\nTop extensions:")
    for ext, count in count_by_ext.most_common():
        size = size_by_ext[ext]
        print(f"  - .{ext:8s}: {count:4d} items, {human_readable_size(size)}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze https://chennai.vit.ac.in/ – estimate pages & data size."
    )
    parser.add_argument(
        "-m",
        "--max-pages",
        type=int,
        default=500,
        help="Maximum number of pages (HTML documents) to visit (default: 500)",
    )

    args = parser.parse_args()

    print("NOTE: This only analyzes (doesn't save files) and is for educational use.")
    analyze_site(START_URL, max_pages=args.max_pages)


if __name__ == "__main__":
    main()
