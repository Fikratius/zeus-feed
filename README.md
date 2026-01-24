# zeus-feed

## Adding news sources
Edit `sources.json` at the repo root. Each entry supports:

```json
[
  {
    "url": "https://example.com/rss.xml",
    "source": "Example News",
    "lang": "en",
    "bias_score": 50,
    "left_right_index": 0
  }
]
```

`lang` defaults to `en`, `bias_score` defaults to `50`, `left_right_index` defaults to `0`.
The update script reads this file by default, or you can override the path via the
`SOURCES_JSON` environment variable.
