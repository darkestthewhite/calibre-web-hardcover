# -*- coding: utf-8 -*-
"""
Hardcover metadata provider for Calibre-Web.

Fetches book metadata from Hardcover (https://hardcover.app) using their
GraphQL API. Uses a two-step approach: first searches via Hardcover's
Typesense-backed search endpoint to get ranked results, then fetches full
book details (description, tags, series, ISBN) in a single follow-up query.

Installation:
    Copy this file to:
        <calibre-web>/cps/metadata_provider/hardcover.py

    To protect it from being overwritten by Calibre-Web updates, add it
    to your exclude.txt:
        echo "cps/metadata_provider/hardcover.py" >> /opt/calibre-web/exclude.txt

Configuration:
    Set your Hardcover API token (https://hardcover.app/account/api) as an
    environment variable. In your systemd service file:

        [Service]
        Environment="HARDCOVER_TOKEN=your_token_here"

    Then reload and restart:
        systemctl daemon-reload && systemctl restart calibre-web

Metadata fetched:
    - Title and authors
    - Description / summary
    - Cover image
    - Genres and tags
    - Series name and position
    - ISBN-13 and publisher
    - Publication date
"""

import json
import os
from typing import List, Optional

import requests

import cps.logger as logger
from cps.services.Metadata import Metadata, MetaRecord, MetaSourceInfo

log = logger.create()

HARDCOVER_API_URL = "https://api.hardcover.app/v1/graphql"
HARDCOVER_SITE_URL = "https://hardcover.app/books"

# Uses Hardcover's Typesense-backed search for properly ranked results.
# The `results` field is a raw JSON string returned from Typesense.
SEARCH_QUERY = """
query Search($query: String!, $per_page: Int!) {
  search(query: $query, query_type: "Book", per_page: $per_page, page: 1) {
    results
  }
}
"""

# Fetches full book details for a list of IDs in a single round-trip.
# Uses _in (exact ID match) which is permitted on the Hardcover API —
# note that _ilike and other pattern operators are blocked for regular users.
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


class HardcoverMetadata(Metadata):
    __name__ = "Hardcover"
    __id__ = "hardcover"

    def search(
        self, query: str, generic_cover: str = "", locale: str = "en"
    ) -> Optional[List[MetaRecord]]:
        """Search Hardcover for books matching the given query string."""

        api_token = os.environ.get("HARDCOVER_TOKEN", "").strip()
        if not api_token:
            log.warning(
                "Hardcover: HARDCOVER_TOKEN environment variable is not set. "
                "See https://hardcover.app/account/api to get a token."
            )
            return []

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "calibre-web-hardcover-metadata-provider",
        }

        book_ids = self._search_ids(query, headers)
        if not book_ids:
            log.debug("Hardcover: No results for query '%s'", query)
            return []

        books = self._fetch_books(book_ids, headers)
        if not books:
            return []

        # Re-order books to match the Typesense search ranking
        id_order = {bid: idx for idx, bid in enumerate(book_ids)}
        books.sort(key=lambda b: id_order.get(b.get("id"), 999))

        results = []
        for book in books:
            try:
                record = self._build_record(book, generic_cover)
                if record:
                    results.append(record)
            except Exception as e:
                log.warning(
                    "Hardcover: Failed to parse book %s: %s", book.get("id"), e
                )

        log.debug(
            "Hardcover: Returning %d results for query '%s'", len(results), query
        )
        return results

    def _search_ids(self, query: str, headers: dict) -> List[int]:
        """Search Hardcover and return a ranked list of book IDs."""
        try:
            resp = requests.post(
                HARDCOVER_API_URL,
                json={
                    "query": SEARCH_QUERY,
                    "variables": {"query": query, "per_page": 10},
                },
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            log.warning("Hardcover: Search request timed out for query '%s'", query)
            return []
        except Exception as e:
            log.error("Hardcover: Search request failed: %s", e)
            return []

        raw = data.get("data", {}).get("search", {}).get("results")
        if not raw:
            return []

        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            hits = parsed.get("hits", [])
            return [
                int(h["document"]["id"])
                for h in hits
                if h.get("document", {}).get("id")
            ]
        except Exception as e:
            log.warning("Hardcover: Failed to parse search hits: %s", e)
            return []

    def _fetch_books(self, ids: List[int], headers: dict) -> List[dict]:
        """Fetch full book details for a list of Hardcover book IDs."""
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
        except requests.exceptions.Timeout:
            log.warning("Hardcover: Book detail request timed out")
            return []
        except Exception as e:
            log.error("Hardcover: Book detail request failed: %s", e)
            return []

        return data.get("data", {}).get("books", [])

    def _build_record(self, book: dict, generic_cover: str) -> Optional[MetaRecord]:
        """Convert a Hardcover book dict into a Calibre-Web MetaRecord."""
        book_id = book.get("id")
        title = (book.get("title") or "").strip()
        if not title:
            return None

        authors = [
            c["author"]["name"]
            for c in book.get("contributions", [])
            if c.get("author") and c["author"].get("name")
        ]

        image = book.get("image") or {}
        cover = image.get("url") or generic_cover

        description = book.get("description") or ""

        # cached_tags comes back as {"Genre": ["Fantasy", "Fiction"], "Mood": ["Dark"]}
        # Flatten all category lists into a single tag list.
        cached_tags = book.get("cached_tags") or {}
        tags = []
        if isinstance(cached_tags, dict):
            for tag_list in cached_tags.values():
                if isinstance(tag_list, list):
                    tags.extend(str(t) for t in tag_list if t)
        elif isinstance(cached_tags, list):
            tags = [str(t) for t in cached_tags if t]

        # Use the first series entry if present
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

        # Normalise release_date to YYYY-MM-DD regardless of what Hardcover returns
        release_date = book.get("release_date") or ""
        if len(release_date) >= 10:
            published_date = release_date[:10]
        elif len(release_date) == 4:
            published_date = release_date + "-01-01"
        else:
            published_date = ""

        slug = book.get("slug") or str(book_id)
        identifiers = {"hardcover": str(book_id)}
        if isbn:
            identifiers["isbn"] = isbn

        return MetaRecord(
            id=str(book_id),
            title=title,
            authors=authors,
            url=f"{HARDCOVER_SITE_URL}/{slug}",
            cover=cover,
            description=description,
            series=series_name,
            series_index=series_index,
            tags=tags,
            publisher=publisher,
            publishedDate=published_date,
            identifiers=identifiers,
            source=MetaSourceInfo(
                id=self.__id__,
                description=self.__name__,
                link="https://hardcover.app",
            ),
        )
