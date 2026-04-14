# Contributing

## Before you open a PR

- Run [`test_hardcover.py`](test_hardcover.py) with a valid `HARDCOVER_TOKEN` after changing anything that touches search, fetch, or parsing. See the README section **Testing without Calibre-Web**.
- Keep edits focused: the plugin is a single file, [`hardcover.py`](hardcover.py), plus the standalone test script.

## Hardcover API changes

Search and book detail behaviour live in the GraphQL strings at the top of `hardcover.py` (`SEARCH_QUERY`, `BOOKS_BY_IDS_QUERY`). If Hardcover changes schema or field names, update those queries and any parsing in `_build_record` / `_search_ids`.

## Issues

If something breaks in production, include the relevant Calibre-Web log lines (see the bug report template).
