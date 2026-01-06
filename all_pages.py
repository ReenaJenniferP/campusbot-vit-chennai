import os
import time
from collections import deque
from urllib.parse import urlparse, urljoin, urldefrag

import requests
from bs4 import BeautifulSoup
import urllib3


# ---- CONFIG ----
START_URL = "https://chennai.vit.ac.in/"
START_DOMAIN = urlparse(START_URL).netloc

# Time between requests (seconds). You can lower this, but be kind :)
REQUEST_DELAY = 0.1

# Disable SSL warnings since we'll use verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def normalize_url(url: str) -> str:
    """Remove fragments and normalize trailing slash."""
    url, _ = urldefrag(url)
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
    """Return lowercase file extension like 'pdf', 'jpg', or '' if none."""
    path = urlparse(url).path
    if not path:
        return ""
    filename = os.path.basename(path)
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def is_probable_page(url: str) -> bool:
    """
    Decide if a URL is likely an HTML page that we want to crawl.
    We treat URLs without extension or with .html/.htm as pages.
    """
    ext = get_extension(url)
    if ext in ("", "html", "htm", "php", "asp", "aspx"):
        return True
    return False


def crawl_all_pages(start_url: str):
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "VITChennaiPageCrawler/1.0 (+university project)"}
    )

    # URLs we will treat as "pages" and actually request
    to_visit = deque([normalize_url(start_url)])
    visited_pages = set()

    # Other resources (pdf, images, etc.) that we see in links but don't fetch
    other_resources = set()

    while to_visit:
        current = to_visit.popleft()
        current = normalize_url(current)

        if current in visited_pages:
            continue
        if not is_same_domain(current, START_DOMAIN):
            continue

        print(f"[{len(visited_pages)+1}] Visiting page: {current}")
        visited_pages.add(current)

        try:
            resp = session.get(current, timeout=15, verify=False)
        except Exception as e:
            print(f"  ! Error fetching {current}: {e}")
            continue

        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()

        # If this isn't HTML, don't try to parse it. Just continue.
        if "text/html" not in content_type and content_type != "":
            print(f"  ! Non-HTML content-type ({content_type}), skipping link parsing.")
            continue

        # Parse HTML to find more links
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  ! Error parsing HTML {current}: {e}")
            continue

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            # Skip obvious non-page hrefs
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            absolute = urljoin(current + "/", href)
            absolute = normalize_url(absolute)

            if not is_same_domain(absolute, START_DOMAIN):
                continue

            if is_probable_page(absolute):
                # HTML-like page: enqueue if new
                if absolute not in visited_pages and absolute not in to_visit:
                    to_visit.append(absolute)
            else:
                # Likely a file (pdf, image, etc.)
                other_resources.add(absolute)

        # polite delay
        time.sleep(REQUEST_DELAY)

    return visited_pages, other_resources


def main():
    print("Starting full crawl of pages under https://chennai.vit.ac.in/ ...")
    pages, resources = crawl_all_pages(START_URL)

    print("\n=== CRAWL COMPLETE ===")
    print(f"Total HTML-like pages found: {len(pages)}")
    print(f"Other linked resources (pdf/img/etc.): {len(resources)}")

    # Save lists to files so you can inspect them
    with open("vit_chennai_pages.txt", "w", encoding="utf-8") as f:
        for url in sorted(pages):
            f.write(url + "\n")

    with open("vit_chennai_other_resources.txt", "w", encoding="utf-8") as f:
        for url in sorted(resources):
            f.write(url + "\n")

    print("\nSaved:")
    print("  - vit_chennai_pages.txt          (all page URLs)")
    print("  - vit_chennai_other_resources.txt (pdf/images/etc. URLs)")


if __name__ == "__main__":
    main()
