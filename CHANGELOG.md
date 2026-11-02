# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed
- Tag import now extracts names from Hardcover tag objects instead of dumping raw dicts into Calibre-Web
- Tag import casefold-dedupes and splits compound names to avoid Calibre-Web `UNIQUE constraint failed: tags.name`

## [1.0.0] - 2026-03-28

### Added
- Initial release
- Two-step GraphQL search: Typesense-ranked search + full detail fetch
- Metadata fields: title, authors, description, cover, genres/tags, series, ISBN-13, publisher, publication date
- Graceful degradation when `HARDCOVER_TOKEN` is not set
- Search result ordering preserved from Typesense relevance ranking
- `release_date` normalisation to `YYYY-MM-DD` regardless of source format
- `cached_tags` flattening from Hardcover's categorised tag dict
