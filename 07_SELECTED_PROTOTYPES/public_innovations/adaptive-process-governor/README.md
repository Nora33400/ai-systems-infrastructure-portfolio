# adaptive-process-governor

Moteur de scoring de process pour proposer des fermetures non critiques.

## Demo

```bash
python main.py --processes '[
  {"pid":1200,"name":"chrome.exe","rss_mb":1400,"cpu_pct":22.1},
  {"pid":88,"name":"System","rss_mb":210,"cpu_pct":1.2},
  {"pid":777,"name":"Code.exe","rss_mb":960,"cpu_pct":18.0}
]'
```

## Portfolio note

This copy contains only the deterministic local demonstration. Publication helpers from the source export were intentionally excluded.
