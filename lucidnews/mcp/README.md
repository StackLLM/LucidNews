# LucidNews MCP

LucidNews includes a built-in MCP server that exposes the native LucidNews pipeline as staged tools and read-only resources.

The MCP layer does not reimplement LucidNews business logic. It reuses the existing fetch, score, filter, enrich, and summarize modules from the main codebase.

## Tools

| Tool | Description |
| --- | --- |
| `ln_validate_config` | Validate LucidNews config and required environment variables |
| `ln_fetch_items` | Fetch and deduplicate content into the `raw` stage |
| `ln_score_items` | Score items from a stage into `scored` |
| `ln_filter_items` | Filter scored items into `filtered` |
| `ln_enrich_items` | Enrich filtered items into `enriched` |
| `ln_generate_summary` | Generate markdown from a stage |
| `ln_run_pipeline` | Run fetch -> score -> filter -> enrich -> summarize |
| `ln_list_runs` | List recent run artifacts |
| `ln_get_run_meta` | Read metadata for a run |
| `ln_get_run_stage` | Read items from a run stage |
| `ln_get_run_summary` | Read a generated summary |
| `ln_get_metrics` | Read in-memory server metrics |

## Resources

- `lucidnews://server/info`
- `lucidnews://metrics`
- `lucidnews://runs`
- `lucidnews://runs/{run_id}/meta`
- `lucidnews://runs/{run_id}/items/{stage}`
- `lucidnews://runs/{run_id}/summary/{language}`
- `lucidnews://config/effective`

## Install and Start

```bash
uv sync
uv run lucidnews-mcp
```

| Option | Default | Description |
|--------|---------|-------------|
| `-l`, `--log-level LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |

The server runs over stdio and is intended to be launched by an MCP client. Stdout is reserved for the MCP protocol; progress, logs, warnings, and errors are written to stderr through one shared Rich console.

## Run Artifacts

Each run writes artifacts under `data/mcp-runs/<run_id>/`:

- `meta.json`
- `raw_items.json`
- `scored_items.json`
- `filtered_items.json`
- `enriched_items.json`
- `summary-<lang>.md`

## Design Principles

1. Keep LucidNews as the single source of business logic.
2. Preserve staged re-entry so a run can continue from intermediate artifacts.
3. Default to no extra side effects unless explicitly requested.

## Client Setup

See [integration.md](integration.md).
