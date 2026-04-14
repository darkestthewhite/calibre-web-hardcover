#!/usr/bin/env python3
"""
Standalone test script for the Hardcover metadata provider.

Exercises the provider against the real Hardcover API without needing
a full Calibre-Web installation. Useful for verifying your token and
checking that the API responses parse correctly.

Usage:
    export HARDCOVER_TOKEN=your_token_here
    python test_hardcover.py

    # Or pass the token inline:
    HARDCOVER_TOKEN=your_token python test_hardcover.py

    # Test a specific query:
    python test_hardcover.py "Mistborn"
"""

import json
import os
import sys
import textwrap

import requests

# Windows consoles often use cp1252; UTF-8 avoids UnicodeEncodeError on ✓/✗/⚠/→
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HARDCOVER_API_URL = "https://api.hardcover.app/v1/graphql"
HARDCOVER_SITE_URL = "https://hardcover.app/books"

SEARCH_QUERY = """
query Search($query: String!, $per_page: Int!) {
  search(query: $query, query_type: "Book", per_page: $per_page, page: 1) {
    results
  }
}
"""

BOOKS_BY_IDS_QUERY = """
query BooksByIds($ids: [Int!]!) {
  books(where: { id: { _in: $ids } }) {
    id
    title
    slug
    description
    release_date
    cached_tags
    image { url }
    contributions {
      author { name }
    }
    book_series {
      position
      series { name }
    }
    default_physical_edition {
      isbn_13
      publisher { name }
    }
  }
}
"""

# ── ANSI colours ─────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):    print(f"{GREEN}  ✓ {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}  ⚠ {msg}{RESET}")
def fail(msg):  print(f"{RED}  ✗ {msg}{RESET}")
def info(msg):  print(f"{CYAN}  → {msg}{RESET}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_token() -> str:
    token = os.environ.get("HARDCOVER_TOKEN", "").strip()
    if not token:
        fail("HARDCOVER_TOKEN is not set.")
        print("  Get one at: https://hardcover.app/account/api")
        sys.exit(1)
    return token


def make_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "calibre-web-hardcover-metadata-provider/test",
    }


def normalise_date(release_date: str) -> str:
    if len(release_date) >= 10:
        return release_date[:10]
    elif len(release_date) == 4:
        return release_date + "-01-01"
    return ""


def flatten_tags(cached_tags) -> list:
    tags = []
    if isinstance(cached_tags, dict):
        for tag_list in cached_tags.values():
            if isinstance(tag_list, list):
                tags.extend(str(t) for t in tag_list if t)
    elif isinstance(cached_tags, list):
        tags = [str(t) for t in cached_tags if t]
    return tags

# ── Test steps ────────────────────────────────────────────────────────────────

def test_token(token: str, headers: dict) -> bool:
    header("1. Token validation")
    try:
        resp = requests.post(
            HARDCOVER_API_URL,
            json={"query": "{ __typename }"},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("data", {}).get("__typename"):
            ok("Token is valid and API is reachable")
            return True
        else:
            fail(f"Unexpected response: {data}")
            return False
    except requests.exceptions.Timeout:
        fail("Request timed out — is the Hardcover API reachable?")
        return False
    except Exception as e:
        fail(f"API request failed: {e}")
        return False


def test_search(query: str, headers: dict) -> list:
    header(f"2. Search — '{query}'")
    try:
        resp = requests.post(
            HARDCOVER_API_URL,
            json={
                "query": SEARCH_QUERY,
                "variables": {"query": query, "per_page": 5},
            },
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        fail(f"Search failed: {e}")
        return []

    raw = data.get("data", {}).get("search", {}).get("results")
    if not raw:
        warn("Search returned no results")
        return []

    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        hits = parsed.get("hits", [])
        ids = [int(h["document"]["id"]) for h in hits if h.get("document", {}).get("id")]
    except Exception as e:
        fail(f"Failed to parse search hits: {e}")
        return []

    ok(f"Found {len(ids)} result(s): {ids}")
    return ids


def test_fetch(ids: list, headers: dict) -> list:
    header("3. Fetch book details")
    if not ids:
        warn("No IDs to fetch — skipping")
        return []

    try:
        resp = requests.post(
            HARDCOVER_API_URL,
            json={
                "query": BOOKS_BY_IDS_QUERY,
                "variables": {"ids": ids},
            },
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        fail(f"Fetch failed: {e}")
        return []

    books = data.get("data", {}).get("books", [])
    ok(f"Fetched {len(books)} book(s)")
    return books


def test_parsing(books: list) -> bool:
    header("4. Parse and validate records")
    if not books:
        warn("No books to parse — skipping")
        return False

    all_ok = True
    for book in books:
        book_id = book.get("id")
        title = (book.get("title") or "").strip()

        if not title:
            fail(f"Book {book_id} has no title")
            all_ok = False
            continue

        authors = [
            c["author"]["name"]
            for c in book.get("contributions", [])
            if c.get("author") and c["author"].get("name")
        ]

        image = book.get("image") or {}
        cover = image.get("url") or ""

        tags = flatten_tags(book.get("cached_tags") or {})

        series_name = None
        series_index = 0.0
        for entry in book.get("book_series") or []:
            s = (entry.get("series") or {}).get("name")
            if s:
                series_name = s
                try:
                    series_index = float(entry.get("position") or 0)
                except (ValueError, TypeError):
                    pass
                break

        edition = book.get("default_physical_edition") or {}
        isbn = edition.get("isbn_13") or ""
        publisher = (edition.get("publisher") or {}).get("name") or ""
        published_date = normalise_date(book.get("release_date") or "")

        slug = book.get("slug") or str(book_id)
        url = f"{HARDCOVER_SITE_URL}/{slug}"

        # Validate date format
        date_ok = (
            not published_date
            or (len(published_date) == 10 and published_date[4] == "-" and published_date[7] == "-")
        )
        if not date_ok:
            fail(f"  [{title}] Bad date format: '{published_date}'")
            all_ok = False

        # Print summary
        print(f"\n  {BOLD}{title}{RESET}")
        info(f"Authors:   {', '.join(authors) or '—'}")
        info(f"Cover:     {'yes (' + cover[:60] + '…)' if cover else 'none'}")
        info(f"Tags:      {', '.join(tags[:5]) + ('…' if len(tags) > 5 else '') if tags else '—'}")
        info(f"Series:    {f'{series_name} #{series_index}' if series_name else '—'}")
        info(f"ISBN-13:   {isbn or '—'}")
        info(f"Publisher: {publisher or '—'}")
        info(f"Published: {published_date or '—'}")
        info(f"URL:       {url}")
        if book.get("description"):
            snippet = textwrap.shorten(book["description"], width=120, placeholder="…")
            info(f"Desc:      {snippet}")

    return all_ok


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "The Name of the Wind"

    print(f"{BOLD}Hardcover metadata provider — test run{RESET}")
    print(f"Query: '{query}'")

    token = get_token()
    headers = make_headers(token)

    if not test_token(token, headers):
        sys.exit(1)

    ids = test_search(query, headers)
    books = test_fetch(ids, headers)
    success = test_parsing(books)

    header("Summary")
    if success and books:
        ok("All checks passed")
    elif books:
        warn("Some checks failed — see above")
        sys.exit(1)
    else:
        fail("No results returned")
        sys.exit(1)


if __name__ == "__main__":
    main()
