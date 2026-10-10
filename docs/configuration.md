---
layout: default
title: Configuration Guide
---

# Configuration Guide

LucidNews is configured through a `.env` file for secrets, a JSON file for runtime settings, and processing profiles for analysis and enrichment prompts. The JSON file defaults to `data/config.json`; profiles default to `profiles/`.

## Configuration Paths

`lucidnews`, `lucidnews-wizard` and `lucidnews-webhook` all resolve configuration and state paths the same way:

| Option | Effect |
| --- | --- |
| `-d`, `--data-dir PATH` | Changes the state directory used for summaries, subscribers, and the default `<data-dir>/config.json` path. |
| `-c`, `--config PATH` | Uses an explicit config file without changing the state directory. |

```bash
uv run lucidnews --data-dir /srv/lucidnews
uv run lucidnews --config /etc/lucidnews/config.json
uv run lucidnews --data-dir /srv/lucidnews --config /etc/lucidnews/config.json
```

When both options are present, configuration is loaded from `--config`, while summaries and subscribers remain under `--data-dir`. Because this logic is identical across all three CLIs, passing the same `-d`/`-c` flags to each one keeps them pointed at the same files — for example, generating a config with `lucidnews-wizard --data-dir /srv/lucidnews`, then running `lucidnews --data-dir /srv/lucidnews` and testing with `lucidnews-webhook --data-dir /srv/lucidnews`.

Without either flag, all three default to `data/config.json`. To bootstrap a custom location without the wizard, initialize it manually:

```bash
mkdir -p /etc/lucidnews
cp data/config.example.json /etc/lucidnews/config.json
```

## Interactive Wizard

`lucidnews-wizard` asks about your interests and generates `data/config.json` from matched presets and, optionally, AI recommendations:

```bash
uv run lucidnews-wizard
```

| Option | Default | Description |
|--------|---------|-------------|
| `-d`, `--data-dir PATH` | `data` | Path to the data directory |
| `-c`, `--config PATH` | `<data-dir>/config.json` | Path to config file |
| `-l`, `--log-level LEVEL` | `WARNING` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |

## Terminal Icons

The `display.icon_style` setting controls icons printed to the terminal:

```json
{
  "display": {
    "icon_style": "nerd"
  }
}
```

Supported styles:

| Value | Description |
| --- | --- |
| `emoji` | Color emoji icons. This is the default when `display` is omitted. |
| `nerd` | Monochrome Nerd Font icons. Requires a Nerd Font in the terminal. |
| `ascii` | ASCII-only markers for terminals without Unicode icon support. |

This setting affects terminal output only. Icons embedded in generated Markdown
and webhook message content are unchanged.

## Processing Profiles

Profiles define how to evaluate and present content; the runtime configuration
defines what you collect, how much you keep, and where it goes. Use `tech-news`
for events and context, `tech-blog` for engineering lessons, `ai-creator` for
market developments, or `ai-creator` for content ideas.

The `processing` section controls profile discovery and the fallback used when
automatic matching cannot select a profile:

```json
{
  "processing": {
    "profiles_dir": "profiles",
    "default_profile": "tech-news",
    "profile_settings": {
      "tech-news": {
        "threshold": 7.0,
        "topic_dedup": true
      },
      "tech-blog": {
        "threshold": 4.0,
        "topic_dedup": false
      }
    }
  }
}
```

- `profiles_dir`: Directory containing one subdirectory per processing profile.
- `default_profile`: ID of a profile present in `profiles_dir`.
- `profile_settings`: User preferences keyed by profile ID. `threshold` accepts
  `0` through `10` or `null` for no score filter; `topic_dedup` defaults to
  `true`. Unknown profile IDs are rejected when LucidNews starts.

Each profile owns its matching, analysis, and enrichment behavior. Runtime
filtering preferences stay in the main JSON configuration. See [Processing
Profiles](profiles.md) for the file layout, complete schema, source routing
rules, and block tool permissions.

## AI Providers

Configure which AI model analyzes and enriches your content.

`api_key_env` is always an environment variable name, not the API key value.
Store secrets in `.env` or your shell environment, then point `api_key_env` at
that variable:

```bash
OPENAI_API_KEY=sk-your-key
GOOGLE_API_KEY=your-gemini-key
```

When LucidNews starts, environment variables have priority because
the active config file does not store the secret. For local VS Code runs, create
`.env` in the repository root and launch LucidNews from that same root directory.

Common API key variable names:

| Provider | `api_key_env` value |
| --- | --- |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` |
| Gemini | `GOOGLE_API_KEY` |
| MiniMax | `MINIMAX_API_KEY` |
| Aliyun DashScope | `DASHSCOPE_API_KEY` |
| Doubao | `DOUBAO_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |

**Anthropic Claude**:

```json
{
  "ai": {
    "provider": "anthropic",
    "model": "claude-sonnet-4.5-20250929",
    "api_key_env": "ANTHROPIC_API_KEY",
    "throttle_sec": 0
  }
}
```

**OpenAI**:

```json
{
  "ai": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY",
    "throttle_sec": 0
  }
}
```

**Gemini**:

```json
{
  "ai": {
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "api_key_env": "GOOGLE_API_KEY",
    "throttle_sec": 0
  }
}
```

**Azure OpenAI**:

```json
{
  "ai": {
    "provider": "azure",
    "model": "gpt-4o-production",
    "api_key_env": "AZURE_OPENAI_API_KEY",
    "azure_endpoint_env": "AZURE_OPENAI_ENDPOINT",
    "api_version": "2024-10-21",
    "throttle_sec": 0
  }
}
```

Set `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` in your `.env`. The `model` field should be your Azure deployment name, not just the base model family name.

**MiniMax**:

The built-in provider defaults to `MiniMax-M3` and the global
OpenAI-compatible endpoint:

```json
{
  "ai": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "api_key_env": "MINIMAX_API_KEY",
    "base_url": "https://api.minimax.io/v1",
    "throttle_sec": 0
  }
}
```

Available models: `MiniMax-M3`, `MiniMax-M2.7`, `MiniMax-M2.7-highspeed`.

Use the endpoint for your account region and preferred compatible API:

| Region | OpenAI-compatible base URL | Anthropic-compatible base URL |
| --- | --- | --- |
| Global | `https://api.minimax.io/v1` | `https://api.minimax.io/anthropic` |
| China | `https://api.minimaxi.com/v1` | `https://api.minimaxi.com/anthropic` |

For the Anthropic-compatible API, keep `provider` set to `minimax` and pass
the base URL directly without adding `/v1`. LucidNews selects its Anthropic
client for this endpoint, and the SDK appends `/v1/messages` when sending a
request:

```json
{
  "ai": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "api_key_env": "MINIMAX_API_KEY",
    "base_url": "https://api.minimax.io/anthropic",
    "throttle_sec": 0
  }
}
```

**Aliyun DashScope** (OpenAI-compatible):

```json
{
  "ai": {
    "provider": "ali",
    "model": "qwen-plus",
    "api_key_env": "DASHSCOPE_API_KEY",
    "throttle_sec": 0
  }
}
```

Use the [DashScope compatible-mode](https://help.aliyun.com/zh/dashscope/developer-reference/use-dashscope-by-calling-openai-api) endpoint. Set `DASHSCOPE_API_KEY` in your `.env`. Optional: set `base_url` to override the default `https://dashscope.aliyuncs.com/compatible-mode/v1`.

**Ollama**:

```json
{
  "ai": {
    "provider": "ollama",
    "model": "llama3.1",
    "api_key_env": "",
    "base_url": "http://192.168.1.10:11434",
    "throttle_sec": 0
  }
}
```

Omit `base_url` to use the default `http://localhost:11434/v1`.
For remote Ollama servers, set `ai.base_url` in the active config file or set
`LUCIDNEWS_OLLAMA_BASE_URL` in `.env`. `OLLAMA_BASE_URL` and `OLLAMA_HOST` are
also recognized. If the value omits `/v1`, LucidNews appends it automatically
for Ollama's OpenAI-compatible endpoint.

### AI request quota

Set `max_requests_per_minute` to the provider's per-minute quota. Every AI call
(classification, analysis, topic dedup, enrichment) shares one budget per
provider/model, so the run stays under the quota instead of losing items to
`429` errors (an item the AI fails to score is never published):

```json
{
  "ai": {
    "max_requests_per_minute": 5
  }
}
```

Free tiers can also have a **daily** cap (for example 20 requests per day per
model); a full run needs roughly two calls per fetched item plus enrichment
calls per selected item and language, so use a paid tier or a model with a
larger quota for production.

### Token budget and exhausted quota

`ai.max_tokens_per_run` (default `null`, no budget) caps the tokens one run may
use across every AI stage. A typical 24-hour run with two languages used about
140,000 tokens; `200000` leaves some margin:

```json
{
  "ai": {
    "max_tokens_per_run": 200000
  }
}
```

The AI is out of quota for the rest of a run when the run reaches this budget,
or when the provider says its quota is used up (Gemini daily quota, OpenAI
`insufficient_quota`, Anthropic or DeepSeek balance). From then on:

- no AI call is made any more: nothing waits, nothing is retried, the run ends normally;
- items not analyzed yet are marked `ai_skipped` and retried in the next run (this uses none of `archive.max_analysis_attempts`);
- items already analyzed keep their analysis, without enrichment if it was not done yet;
- up to `digest.unanalyzed_max_items` (default `15`, `0` to publish none) unanalyzed items are published in a separate **Not analyzed by the AI** section: original headline, source and link only, always labeled `unverified`, best-known publishers first.

A per-minute rate limit (`429` with a per-minute quota) is not an exhausted
quota: it is retried as before, and an item that still fails is left out.
Each run records why the AI stopped (`ai_limit`), the tokens used and the number
of unanalyzed items.

### Failed-item retry

`ai.failed_retry_delay_sec` (default `30`): items whose analysis or enrichment
failed are retried once at the end of that stage after this pause, which lets a
per-minute quota reset. Set it to `null` to disable the in-run retry.

### AI throttling

If your model has a strict per-minute request cap, you can also slow the scorer down in the active config file:

```json
{
  "ai": {
    "throttle_sec": 4.5
  }
}
```

- `throttle_sec`: Pause between scored items in seconds. Default is `0`.
- `4.5` is a reasonable starting point for free-tier models capped around 15 requests per minute.
- Set it back to `0` if you have enough throughput headroom and want maximum speed.

### AI Concurrency

By default, AI scoring and enrichment run one item at a time. If your API endpoint supports concurrent requests, you can increase throughput:

```json
{
  "ai": {
    "analysis_concurrency": 4,
    "enrichment_concurrency": 2
  }
}
```

- `analysis_concurrency`: Number of items scored in parallel. Default is `1`.
- `enrichment_concurrency`: Number of high-scoring items enriched in parallel. Default is `1`.
- Both values are clamped to a minimum of `1`.
- Preserve the existing retry behavior per item.
- Result ordering is preserved regardless of concurrency.
- If you also use `throttle_sec`, each concurrent task sleeps independently after finishing an item.

**Custom Base URL** (for proxies):

```json
{
  "ai": {
    "provider": "anthropic",
    "base_url": "https://your-proxy.com/v1",
    ...
  }
}
```

For OpenAI-compatible gateways, LucidNews sends `temperature` by default. If a newer reasoning-style model rejects that parameter with an error such as `temperature is deprecated for this model`, LucidNews retries once without it and remembers that capability for later requests.

## Information Sources

All sources are configured under the top-level `sources` key in `config.json`.
Source entries also accept `profile`:

| Value | Behavior |
| --- | --- |
| `"tech-blog"` | Use that profile directly, without an AI matching call |
| `"auto"` or omitted | Let AI choose one of all loaded profiles |
| `["tech-news", "ai-creator"]` | Let AI choose one profile from this candidate list |

An unknown profile ID is an error. For nested sources, set the field on the
item-producing entry, such as an RSS feed, Reddit subreddit or user, Telegram
channel. See [Source Routing](profiles.md#source-routing)
for validation and fallback rules.

### GitHub

```json
{
  "sources": {
    "github": [
      {
        "type": "user_events",
        "username": "gvanrossum",
        "enabled": true,
        "category": "oss",
        "profile": "tech-news"
      },
      {
        "type": "repo_releases",
        "owner": "python",
        "repo": "cpython",
        "enabled": true,
        "category": "oss"
      }
    ]
  }
}
```

### Hacker News

```json
{
  "sources": {
    "hackernews": {
      "enabled": true,
      "fetch_top_stories": 30,
      "min_score": 100,
      "category": "tech"
    }
  }
}
```

### RSS Feeds

```json
{
  "sources": {
    "rss": [
      {
        "name": "Blog Name",
        "url": "https://example.com/feed.xml",
        "enabled": true,
        "category": "ai-ml",
        "profile": "auto"
      }
    ]
  }
}
```

### Reddit

Reddit scraping is free and does not require API keys. Subreddit posts and comments prefer `old.reddit.com`; JSON and RSS endpoints are used as fallbacks when needed.

```json
{
  "sources": {
    "reddit": {
      "enabled": true,
      "fetch_comments": 5,
      "subreddits": [
        {
          "subreddit": "MachineLearning",
          "sort": "hot",
          "fetch_limit": 25,
          "min_score": 10,
          "category": "ai-ml"
        }
      ],
      "users": [
        {
          "username": "spez",
          "sort": "new",
          "fetch_limit": 10,
          "category": "social"
        }
      ]
    }
  }
}
```

### Telegram

Telegram scraping uses the public web preview at `https://t.me/s/<channel>`, so no API key is required. Only public channels are supported.

```json
{
  "sources": {
    "telegram": {
      "enabled": true,
      "channels": [
        {
          "channel": "zaihuapd",
          "enabled": true,
          "fetch_limit": 20,
          "category": "ai-news"
        }
      ]
    }
  }
}
```

- `enabled` — enable or disable Telegram fetching globally
- `channels` — list of public Telegram channels to monitor
- `channel` — Telegram channel username only, without `@` or the full `https://t.me/` URL
- `fetch_limit` — maximum number of recent messages to inspect per channel per run (default: `20`)
- `category` — optional tag for balanced digest grouping (e.g., `"ai"`, `"cybersecurity"`)

### Twitter

Requires an [Apify](https://apify.com) account. Set `APIFY_TOKEN` in your `.env` file. The free tier includes $5/month of credit, enough for roughly 20,000 tweets.

```json
{
  "sources": {
    "twitter": {
      "enabled": true,
      "users": ["karpathy", "ylecun"],
      "keywords": ["LLM", "open source"],
      "fetch_limit": 10,
      "category": "social",
      "fetch_reply_text": false,
      "max_replies_per_tweet": 3,
      "max_tweets_to_expand": 10,
      "reply_min_likes": 5
    }
  }
}
```

- `users` — Twitter screen names to monitor, without the `@` prefix
- `keywords` — independent X search queries fetched via Apify scweet `source_mode: "search"`. These search beyond the configured `users`; they do not filter those users' timelines. Playwright mode logs a warning and skips keyword fetching.
- `fetch_limit` — in Apify mode, the requested tweet limit per actor run is `max(100, fetch_limit)`. All configured users share one profile run, and each non-empty keyword query starts a separate search run. This is not a total limit for the Twitter source.
- `category` — optional tag for balanced digest grouping (applies to all tweets from this source)
- `fetch_reply_text` — when `true`, fetch actual reply bodies for important tweets and append them under `--- Top Comments ---` so the AI can factor in community discussion. Disabled by default.
- `max_replies_per_tweet` — maximum reply lines to append per tweet (default: 3)
- `max_tweets_to_expand` — cap on how many tweets get reply expansion per run, to control Apify credit usage (default: 10)
- `reply_min_likes` — only include replies with at least this many likes (default: 0)

You can configure users, keywords, or both. Results are filtered to the current time window and merged, with duplicate tweet IDs removed across timelines and searches.

For example, the configuration above starts three discovery runs: one for both users and one for each of the two keywords. Each run requests up to 100 tweets, for up to 300 before time filtering and deduplication. Adding keyword queries increases Apify usage; optional reply expansion starts additional runs.

The scraper uses the `altimis/scweet` actor by default. You can override it with `actor_id` if needed.

### OSS Insight (Trending GitHub Repos)

Pulls top star-gain repositories from the [OSS Insight](https://ossinsight.io) public API, which aggregates GitHub WatchEvents. Useful for surfacing repos that are gaining stars right now without needing to scrape GitHub Trending or query BigQuery.

```json
{
  "sources": {
    "ossinsight": {
      "enabled": true,
      "period": "past_24_hours",
      "languages": ["All", "Python", "TypeScript"],
      "keywords": [],
      "min_stars": 10,
      "max_items": 30,
      "category": "oss-trending"
    }
  }
}
```

- `period` — time window for star-gain ranking. Supported: `past_24_hours`, `past_28_days`. (`past_7_days` is currently broken upstream.)
- `languages` — primary language buckets to query. Use `"All"` for the full ranking, or any GitHub language label such as `"Python"`, `"TypeScript"`, `"Rust"`, `"Jupyter Notebook"`. The scraper fans out one request per language and merges results.
- `keywords` — optional case-insensitive substrings matched against `description`, `collection_names`, and `repo_name`. Only repos containing at least one keyword pass through. Leave empty to ingest everything trending.
- `min_stars` — drop repos with fewer than this many stars gained in the period.
- `max_items` — final cap after merging and sorting by `stars_gained` descending.
- `category` — optional tag for balanced digest grouping (e.g., `"oss-trending"`)

No API key is required.

## Archive

```json
{
  "archive": { "enabled": true, "path": "archive.sqlite3", "reuse_analysis": true }
}
```

- `path`: SQLite file; relative paths resolve under the data directory.
- `retry_failed_analysis`, `retry_window_hours`, `max_analysis_attempts`: an item the AI failed to score is kept as pending and retried in later runs (even outside the time window) while it was first seen less than `retry_window_hours` ago and has failed fewer than `max_analysis_attempts` runs.
- `reuse_analysis`: reuse the stored analysis of an item that comes back unchanged (same title, URL, content and routing) instead of calling the AI again. Turn it off after changing analysis prompts to force a fresh analysis.
- `reuse_enrichment` (default `true`): with a reused analysis, also reuse the stored enrichment (translated title, summary, context) when it exists in every configured language. Adding a language enriches the item again in all languages.
- Archive failures never stop a run; they are logged as warnings.

## Editing settings from the web app

The **Settings** screen (`/settings`, local API only) edits the common settings
of this file and the API keys, without a terminal. See `frontend/README.md`:

- only changed fields are written; `${VARIABLE}` placeholders stay as they are,
  and a field holding one is shown locked;
- every write is validated, atomic, and preceded by a copy in `data/backups/`
  (last 10), which the screen can restore;
- API keys are written to the project's `.env` (mode 600) and never shown again.

Settings take effect at the next run; the API reloads them at once.

The **Sources** screen edits `sources` the same way (raw file, backup, version
check): add an RSS feed, a GitHub repository or account, a subreddit, a Reddit
account or a Telegram channel; edit, enable, disable or delete it; enable and
tune Hacker News, OSS Insight, GDELT and Google News. A feed URL must be public
(no `localhost`, private address or `${VARIABLE}`; put a URL with a token in this
file by hand). **Test** fetches one source with its collector, without AI or
archive, and reports what came back. X (Twitter) stays read only there.

## Reliability

See [fiabilite.md](fiabilite.md) for the model. Configuration:

```json
{
  "reliability": {
    "domains": { "internal-blog.example": "official" },
    "accounts": { "x:openai": "official" },
    "exclude_labels": ["rumor"],
    "corroboration_lookback_hours": 72,
    "corroboration_max_references": 30
  }
}
```

- `domains`: add or override publisher tiers (`official`, `reputable`, `community`, `unknown`). Subdomains are covered; the most specific entry wins.
- `accounts`: tiers for social accounts, keyed `platform:handle` (`x:openai`, `mastodon:user@server`, `bluesky:handle`, `telegram:channel`). A registered account outranks the platform it posts on.
- `exclude_labels`: reliability labels (`confirmed`, `reliable`, `unverified`, `rumor`) removed from the digest. Empty by default: unconfirmed items are published but explicitly flagged.
- `corroboration_lookback_hours` (default `72`): official or reputable items archived in this window can corroborate today's digest items. `0` keeps only the current run (items below the threshold still count).
- `corroboration_max_references` (default `30`): maximum reference items sent with each topic dedup call, most recent first. `0` disables wider corroboration.
- RSS feeds accept `"trust": "<tier>"` to pin the tier of their items.
- After changing `domains` or `accounts`, `uv run lucidnews-reassess` previews the new labels of archived items and `--apply` writes them (no AI call).

### Source quality

`digest.source_quality_days` (default `30`, `0` disables it): window of archived
items used to score each source from 0 to 100 (mean AI score and share of
confirmed or reliable items, smoothed while a source has few items). The score
only breaks ties between items with the same AI score; it is shown by
`lucidnews-sources` and on the Sources screen.

## Filtering

Score filtering is configured under `processing.profile_settings` in the runtime
configuration. Each profile can use a different `threshold`; set it to `null` or
omit that profile's settings to disable score filtering. See [Processing
Profiles](profiles.md#filtering) and [Scoring](scoring.md).

The runtime `collection` section controls the fetch window and contains only
`time_window_hours`:

```json
{
  "collection": {
    "time_window_hours": 24
  }
}
```

- `time_window_hours`: Fetch content from last N hours

The runtime `digest` section controls final section order and optional balanced
digest limits:

```json
{
  "digest": {
    "max_items": 20,
    "profile_order": ["tech-news", "tech-blog", "ai-creator"],
    "category_groups": {
      "ai": {
        "name": "AI / Machine Learning",
        "limit": 5,
        "categories": ["ai-news", "ai-tools", "machine-learning", "llm"]
      },
      "security": {
        "name": "Cybersecurity",
        "limit": 5,
        "categories": ["cybersecurity"]
      }
    },
    "default_group": "other",
    "default_group_limit": 3
  }
}
```

- `max_items`: Optional final cap after all group limits are applied
- `profile_order`: Optional final-summary section priority. When non-empty,
  loaded profiles not listed here are appended in profile discovery order.
  When empty or omitted, sections follow their first appearance in the selected
  items. Unknown or duplicate IDs are rejected. The example prioritizes the
  three listed profiles in that order.
- `category_groups`: Optional map of quota groups. Each group requires a positive
  `limit` and a non-empty `categories` list. Items within each group are kept by
  analysis score, highest first.
- `category_groups.*.name`: Optional display name used in run logs
- `default_group`: Group key for items whose category does not match any
  configured group. Default is `other`.
- `default_group_limit`: Optional positive limit for unmatched items. If omitted,
  unmatched items are unlimited except for `max_items`.

Balanced digest filtering runs after configured profile filtering and topic
deduplication, but before enrichment. This reduces enrichment calls to only the
items that can appear in the final digest.

Group matching uses the source category stored in `ContentItem.metadata.category`.
All source types support a `category` field: `sources.rss[].category`,
`sources.github[].category`, `sources.hackernews.category`,
`sources.reddit.subreddits[].category`, `sources.reddit.users[].category`,
`sources.telegram.channels[].category`, `sources.twitter.category`,
`sources.ossinsight.category`,
`sources.gdelt.category`, and `sources.google_news.category`.
Sources without a category set enter the default group.

If the same category appears in multiple groups, LucidNews logs a warning and uses
the first group in configuration order. Omitting both `category_groups` and
`max_items` disables balanced digest limits; configured profile thresholds still
apply.

## Environment Variable Substitution

Any string value in the active config file supports `${VAR_NAME}` syntax. Variables are expanded at runtime from the environment (including values loaded from `.env`). This lets you keep secrets, tenant-specific endpoints, and private URLs out of the checked-in JSON file.

Example:

```json
{
  "ai": {
    "base_url": "${LUCIDNEWS_AI_BASE_URL}"
  },
  "sources": {
    "rss": [
      {
        "name": "LWN.net",
        "url": "https://lwn.net/headlines/full_text?key=${LWN_KEY}",
        "enabled": true
      }
    ]
  },
  "webhook": {
    "url_env": "LUCIDNEWS_WEBHOOK_URL",
    "headers": "Authorization: Bearer ${LUCIDNEWS_WEBHOOK_TOKEN}"
  }
}
```

- `${NAME}` is replaced only when `NAME` is a valid identifier like `LWN_KEY` or `LUCIDNEWS_AI_BASE_URL`.
- Unset variables are left as `${NAME}` instead of becoming an empty string, so configuration mistakes fail loudly downstream.
- Expansion is recursive through dicts, lists, and tuples; non-string values are left unchanged.

## Email Subscription

Email delivery is optional and disabled unless `email.enabled` is `true`. LucidNews uses SMTP to send daily summaries and IMAP to check subscribe/unsubscribe requests.

```json
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.example.com",
    "smtp_port": 465,
    "smtp_username": null,
    "imap_enabled": true,
    "imap_server": "imap.example.com",
    "imap_port": 993,
    "email_address": "newsletter@example.com",
    "password_env": "EMAIL_PASSWORD",
    "sender_name": "LucidNews",
    "subscribe_keyword": "SUBSCRIBE",
    "unsubscribe_keyword": "UNSUBSCRIBE"
  }
}
```

- `enabled`: Turns email subscription handling and daily email delivery on or off.
- `smtp_server` / `smtp_port`: SMTP server used to send emails.
- `smtp_username`: Optional SMTP login username. If omitted, LucidNews uses `email_address`.
- `imap_enabled`: Turns IMAP subscribe/unsubscribe checks on or off. Set it to `false` for send-only SMTP providers.
- `imap_server` / `imap_port`: IMAP server used to scan incoming subscription requests when `imap_enabled` is `true`.
- `email_address`: Sender account and mailbox checked for subscription requests.
- `password_env`: Environment variable containing the email password or app password. Defaults to `EMAIL_PASSWORD`.
- `sender_name`: Display name shown in sent emails.
- `subscribe_keyword` / `unsubscribe_keyword`: Keywords LucidNews looks for in incoming email subjects.

Resend SMTP example:

```json
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.resend.com",
    "smtp_port": 465,
    "smtp_username": "resend",
    "password_env": "RESEND_API_KEY",
    "imap_enabled": false,
    "imap_server": "",
    "imap_port": 993,
    "email_address": "noreply@example.com",
    "sender_name": "LucidNews"
  }
}
```

Set `RESEND_API_KEY` in `.env`. Recipients are loaded from `<data-dir>/subscribers.json` (`data/subscribers.json` by default).

## Webhook Notification

Webhook notification is optional and disabled unless `webhook.enabled` is `true`. LucidNews can call Feishu/Lark, DingTalk, Slack, Discord, or any custom webhook endpoint when the pipeline succeeds or fails.

```json
{
  "webhook": {
    "enabled": true,
    "url_env": "LUCIDNEWS_WEBHOOK_URL",
    "delivery": "summary",
    "overview_position": "first",
    "platform": "generic",
    "layout": "markdown",
    "fallback_layout": "markdown",
    "languages": null,
    "request_body": {
      "text": "#{message_title}\n#{summary}"
    },
    "headers": ""
  }
}
```

- `enabled`: Turns webhook delivery on or off. The default is `false`.
- `url_env`: Environment variable that contains the webhook URL. For example, set `LUCIDNEWS_WEBHOOK_URL=https://...` in `.env`.
- `delivery`: Controls how messages are sent. Use `summary` for one full message, or `summary_and_items` for one overview message followed by one message per selected item.
- `overview_position`: Controls where the overview is sent in `summary_and_items` mode. Use `first` for the traditional order, or `last` to send item details in reverse and keep the overview as the newest chat message.
- `platform`: Optional webhook platform hint. Use `generic` by default, or `feishu` / `lark` to enable platform-specific card rendering.
- `layout`: Controls the message layout. Use `markdown` for templated Markdown delivery, or `collapsible` with `platform: "feishu"` / `"lark"` for a single Feishu Card JSON 2.0 message with each item in a collapsed panel.
- `fallback_layout`: Reserved fallback layout for unsupported platform/layout combinations. The current safe fallback is `markdown`.
- `languages`: Optional webhook-only language filter. Use `["zh"]` or `["en"]` to send only selected languages; use `null` or omit it to send all configured `ai.languages`.
- `request_body`: Optional request body. If empty, LucidNews sends a `GET` request. If provided, LucidNews sends a `POST` request.
- `headers`: Optional custom headers, one `Key: Value` pair per line.

When `request_body` is a JSON object or array, LucidNews renders placeholders and serializes it as JSON. When it is a string, LucidNews renders it directly and detects JSON if the rendered string is valid JSON.

### Delivery Modes And Layouts

`delivery` controls how many webhook messages LucidNews sends:

- `summary`: Sends one message containing the full daily summary. This is simple, but some chat platforms may reject long messages.
- `summary_and_items`: Sends one overview message plus one message per selected item. In each item message, `#{summary}` contains only that item's Markdown body. This is useful for platforms that reject or truncate long messages.

`layout` controls how each message is rendered:

- `markdown`: Uses your `request_body` template for each message. This is the default and works with generic webhooks, DingTalk, Slack, Discord, Feishu, and Lark.
- `collapsible`: Currently supported for `platform: "feishu"` or `"lark"`. LucidNews ignores `request_body` and builds one Feishu/Lark Card JSON 2.0 message with each item in a collapsed panel.

For platforms without a platform-specific layout, keep `layout: "markdown"` and choose the message count with `delivery`.

Example `summary_and_items` Markdown delivery config:

```json
{
  "webhook": {
    "enabled": true,
    "url_env": "LUCIDNEWS_WEBHOOK_URL",
    "delivery": "summary_and_items",
    "overview_position": "last",
    "platform": "generic",
    "layout": "markdown",
    "request_body": {
      "text": "#{message_title}\n\n#{summary?limit=3000&split=---}"
    }
  }
}
```

With `summary_and_items`, LucidNews sends one overview plus one message per selected item. `overview_position: "last"` sends item messages first and keeps the overview as the newest chat message; omit it or set `"first"` to send the overview first.

### Webhook Templates

Available variables:

| Variable | Description |
|----------|-------------|
| `#{date}` | Report date, for example `2026-04-24` |
| `#{language}` | Language code, such as `en` or `zh` |
| `#{important_items}` | Number of items selected by profile filtering |
| `#{all_items}` | Total number of fetched items |
| `#{result}` | `success` or `failed` |
| `#{timestamp}` | Unix timestamp |
| `#{message_title}` | Message title, such as the daily title, overview title, or item title |
| `#{message_kind}` | Message kind: `summary`, `overview`, `item`, `failure`, or `manual` |
| `#{summary}` | Message Markdown. In `summary_and_items` mode this is the overview or one item body, depending on the message |

When `delivery` is `summary_and_items`, item messages also include:

| Variable | Description |
|----------|-------------|
| `#{item_index}` | 1-based item number |
| `#{item_count}` | Total number of item messages |
| `#{profile_item_index}` | 1-based item number within the current Profile |
| `#{profile_item_count}` | Number of item messages in the current Profile |
| `#{item_profile}` | Current Profile ID |
| `#{item_profile_name}` | Localized current Profile name |
| `#{item_title}` | Current item title |
| `#{item_url}` | Current item URL |
| `#{item_score}` | Current item analysis score |

For webhook delivery, LucidNews flattens HTML disclosure blocks such as `<details><summary>...</summary>` in `#{summary}` into plain Markdown link lists. This makes the generated summary easier to render in chat products. Saved Markdown files, GitHub Pages, and email content are unchanged.

Use `#{key?limit=N&split=DELIM}` to truncate long values by splitting on `DELIM` and keeping segments until the total character count reaches `N`.

```text
#{summary?limit=3000&split=---}
```

### DingTalk

In DingTalk, create a custom group robot and use a custom keyword such as `LucidNews`. The keyword must appear in the body content.

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "LucidNews #{date} Daily",
    "text": "LucidNews result: #{result}\n\nLucidNews important items: #{important_items}/#{all_items}\n\n#{summary}"
  }
}
```

### Feishu / Lark

In Feishu or Lark, create a custom group robot and use a custom keyword such as `LucidNews`. The keyword must appear in the body content.

Use Card JSON 2.0 for Markdown rendering. The card must include `"schema": "2.0"` and put rich-text Markdown components under `card.body.elements`.

To keep the group chat compact while still allowing readers to browse the full briefing inside Feishu, use the collapsible layout:

```json
{
  "webhook": {
    "enabled": true,
    "url_env": "LUCIDNEWS_WEBHOOK_URL",
    "platform": "feishu",
    "layout": "collapsible",
    "fallback_layout": "markdown",
    "languages": ["zh"]
  }
}
```

With this layout, LucidNews sends one interactive card containing the overview and one collapsed panel per selected item. Each panel can be expanded in Feishu to read the full item detail. The regular `request_body` template is ignored for this rendered card.

```json
{
  "msg_type": "interactive",
  "card": {
    "schema": "2.0",
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "#{message_title}"
      },
      "template": "blue"
    },
    "body": {
      "elements": [
        {
          "tag": "markdown",
          "content": "LucidNews result: #{result}\nLucidNews important items: #{important_items}/#{all_items}"
        },
        {
          "tag": "hr"
        },
        {
          "tag": "markdown",
          "content": "#{summary}"
        }
      ]
    }
  }
}
```

### Testing

Use `lucidnews-webhook` to preview or send a test notification without running the full pipeline:

```bash
uv run lucidnews-webhook --dry-run
```

| Option | Default | Description |
|--------|---------|-------------|
| `--lang LANG` | first configured language | Language to test |
| `--dry-run` | off | Preview rendered content without sending |
| `--delivery {summary,summary_and_items}` | value from config | Override delivery mode for this test |
| `-d`, `--data-dir PATH` | `data` | Path to the data directory |
| `-c`, `--config PATH` | `<data-dir>/config.json` | Path to config file |
| `-l`, `--log-level LEVEL` | `WARNING` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |


## MCP Server

LucidNews includes an MCP server for AI assistants and MCP-compatible clients.

```bash
uv run lucidnews-mcp
```

Available tools include `hz_validate_config`, `hz_fetch_items`, `hz_score_items`, `hz_filter_items`, `hz_enrich_items`, `hz_generate_summary`, and `hz_run_pipeline`.

See [`src/mcp/README.md`](../src/mcp/README.md) for the full tool reference and [`src/mcp/integration.md`](../src/mcp/integration.md) for client setup.
