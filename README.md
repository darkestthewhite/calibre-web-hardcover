# calibre-web-hardcover

A [Hardcover](https://hardcover.app) metadata provider plugin for [Calibre-Web](https://github.com/janeczku/calibre-web).

Hardcover is a modern, community-driven book tracking platform. This plugin lets you search and import book metadata directly from Hardcover when editing books in Calibre-Web — including descriptions, cover images, genres, series info, and ISBN.

---

## Features

- **Title and authors**
- **Description / summary**
- **Cover image**
- **Genres and tags** (flattened from Hardcover's category groups)
- **Series name and position**
- **ISBN-13 and publisher**
- **Publication date**
- Results ranked by Hardcover's Typesense search engine (most relevant first)

---

## Requirements

- Calibre-Web (tested on 0.6.23+)
- Python 3.9+
- A free Hardcover account and API token

---

## Installation

### 1. Get a Hardcover API token

1. Log in to [hardcover.app](https://hardcover.app)
2. Go to **Account → API** or navigate directly to [hardcover.app/account/api](https://hardcover.app/account/api)
3. Copy the token shown on that page — it will be a long string starting with `eyJ...`

> **Important:** set the token value only — do **not** include the `Bearer ` prefix.
> The provider adds that automatically.
>
> ✅ Correct: `HARDCOVER_TOKEN=eyJhbGci...`
> ❌ Wrong:   `HARDCOVER_TOKEN=Bearer eyJhbGci...`

### 2. Copy the provider file

Copy `hardcover.py` from this repository into Calibre-Web’s metadata provider directory. Adjust the source path if you cloned to a different location.

```bash
cp hardcover.py /opt/calibre-web/cps/metadata_provider/hardcover.py
```

### 3. Protect from updates

Add the file to Calibre-Web's exclude list so it survives auto-updates:

```bash
echo "cps/metadata_provider/hardcover.py" >> /opt/calibre-web/exclude.txt
```

### 4. Configure your API token

The token is passed as an environment variable called `HARDCOVER_TOKEN`.

**If you are using systemd** (most common), open your service file:

```bash
nano /etc/systemd/system/calibre-web.service
```

Add the `Environment` line inside the `[Service]` block:

```ini
[Service]
WorkingDirectory=/opt/calibre-web
ExecStart=/opt/calibre-web/.venv/bin/python /opt/calibre-web/cps.py
Environment="HARDCOVER_TOKEN=eyJhbGci..."   # ← paste your token here, no Bearer prefix
```

Then reload and restart:

```bash
systemctl daemon-reload
systemctl restart calibre-web
```

**If you are using Docker**, pass it as an environment variable in your `docker-compose.yml`:

```yaml
environment:
  - HARDCOVER_TOKEN=eyJhbGci...
```

**To verify the token was picked up by the process:**

```bash
cat /proc/$(pgrep -f cps.py)/environ | tr '\0' '\n' | grep HARDCOVER
```

You should see `HARDCOVER_TOKEN=eyJ...` printed. If the line is missing, the service file wasn't reloaded correctly.

### 5. Verify it loaded

```bash
journalctl -u calibre-web | grep -i hardcover
```

You should see no errors on startup. If the token is missing you'll see a warning — the provider will gracefully skip rather than crash.

---

## Usage

1. Open any book in Calibre-Web and click **Edit metadata**
2. Click **Get metadata**
3. Select **Hardcover** from the provider list (or leave all enabled)
4. Search by title, author, or both
5. Select a result and click **Save**

---

## How it works

The provider uses a two-step GraphQL approach against the Hardcover API:

1. **Search** — queries Hardcover's Typesense-backed search endpoint to get a ranked list of matching book IDs
2. **Fetch** — retrieves full book details for those IDs in a single follow-up query

This avoids the `_ilike` operator (which is blocked for regular API users) and preserves Typesense's relevance ranking in the results shown to you.

---

## Testing without Calibre-Web

The plugin depends on Calibre-Web’s `cps` modules at runtime. To verify your API token and that Hardcover responses parse correctly, use the standalone script:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate

pip install -r requirements.txt
set HARDCOVER_TOKEN=your_token_here   # Unix: export HARDCOVER_TOKEN=...
python test_hardcover.py
```

Optional query argument: `python test_hardcover.py "Your search query"`.

---

## Known limitations

- **ISBN-10 not supported** — Hardcover only returns ISBN-13 via the API
- **Single series** — if a book belongs to multiple series, only the first is used
- **Rate limits** — Hardcover's API is rate limited. Normal interactive use is well within limits, but bulk operations may trigger throttling
- **No cover upload** — Calibre-Web fetches the cover URL; the image must be publicly accessible from Hardcover's CDN

---

## Contributing

PRs and issues welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to test changes and what to update when Hardcover’s API changes.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

- [Calibre-Web](https://github.com/janeczku/calibre-web) by janeczku and contributors
- [Hardcover](https://hardcover.app) for building an awesome platform for book lovers