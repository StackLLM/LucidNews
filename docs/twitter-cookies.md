# Twitter / X Cookie Setup (Playwright mode)

LucidNews can read X/Twitter in two ways:

| Mode | Cost | Stability | Use case |
|------|------|-----------|----------|
| **Apify** (default) | Paid Apify subscription | High | Production, many accounts |
| **Playwright + cookies** | Free | Medium | Personal use, a few accounts |

This page covers the Playwright mode. Automated access to X is governed by X's
Terms of Service; check that your use is allowed before enabling it, and prefer
the Apify mode for anything beyond personal use.

## 1. Install dependencies

```bash
uv sync --extra twitter
uv run playwright install chromium
```

## 2. Export cookies

### Option A: browser extension

1. Sign in to [x.com](https://x.com) in Chrome, Edge or Firefox.
2. Install a cookie export extension such as **Cookie-Editor**.
3. Export the x.com cookies in **JSON** format.
4. Save them as `data/x_cookies_1.json`.

### Option B: developer tools

1. While signed in, open the developer tools (`F12`).
2. Go to **Application → Cookies → https://x.com**.
3. Copy the `auth_token`, `ct0` and `twid` cookies into a JSON array:

```json
[
  {"name": "auth_token", "value": "<auth_token>", "domain": ".x.com", "path": "/", "secure": true, "httpOnly": true},
  {"name": "ct0", "value": "<ct0>", "domain": ".x.com", "path": "/", "secure": true, "httpOnly": false}
]
```

## 3. Configuration

In `data/config.json`:

```json
{
  "sources": {
    "twitter": {
      "enabled": true,
      "mode": "playwright",
      "users": ["karpathy", "ylecun"],
      "fetch_limit": 10,
      "cookie_dir": "data",
      "cookie_file_pattern": "x_cookies_*.json"
    }
  }
}
```

Keyword search (`sources.twitter.keywords`) is Apify-only. Playwright logs a
warning and skips those queries.

## 4. Several cookie files

Every file matching `cookie_file_pattern` (for example `data/x_cookies_1.json`,
`data/x_cookies_2.json`) is used in turn; when one session is rate-limited the
scraper moves to the next one.

## 5. Proxy (optional)

Playwright reads the `PROXY`, `https_proxy`, `http_proxy` and `all_proxy`
environment variables:

```bash
export https_proxy=http://127.0.0.1:7890
```

## 6. Notes

- Cookies expire (usually after 1–4 weeks); export them again when they do.
- Cookie files are secrets. `data/x_cookies_*.json` is in `.gitignore`; never commit them.
- Keep the fetch volume low to stay within the platform's limits.

## 7. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "No cookie files found" | File name does not match | Check `cookie_file_pattern` and the file names |
| "page shows login gate" | Cookies expired | Sign in again and re-export |
| "no GraphQL data intercepted" | Page changed or rate-limited | Retry later |
| Playwright missing | Optional dependency not installed | `uv sync --extra twitter && uv run playwright install chromium` |
