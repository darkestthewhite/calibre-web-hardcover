---
name: Bug report
about: Report a problem with the Hardcover metadata provider
labels: []
---

**What went wrong**

**Calibre-Web version** (e.g. 0.6.26)

**Python version** (e.g. 3.11)

**Logs**

Hardcover lines from Calibre-Web:

```text
journalctl -u calibre-web | grep -i hardcover
```

If the failure is during metadata fetch, include any GraphQL or HTTP error text from the log.

**Reproduce**

1.
2.

**What you expected**

**Anything else** (Docker, reverse proxy, etc.)
